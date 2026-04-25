from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_engineering_mutation_screening_v0_22_1 import (
    load_jsonl,
    run_executor_case,
    summarize_case,
)
from gateforge.agent_modelica_single_point_family_screening_v0_22_8 import build_repair_cases


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADMISSION_PATH = (
    REPO_ROOT / "artifacts" / "single_point_family_generalization_v0_22_8" / "single_point_family_candidates.jsonl"
)
DEFAULT_REFERENCE_SUMMARY_PATH = REPO_ROOT / "artifacts" / "single_point_family_screening_v0_22_8" / "case_summaries.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "single_point_family_repeatability_v0_22_9"


def _metadata_by_candidate(admitted_rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    return {
        str(row.get("candidate_id") or ""): {
            "source_complexity_class": str(row.get("source_complexity_class") or "unknown"),
            "mutation_family": str(row.get("mutation_pattern") or ""),
        }
        for row in admitted_rows
        if row.get("candidate_id")
    }


def annotate_observation(row: dict[str, Any], *, run_id: str, metadata: dict[str, dict[str, str]]) -> dict[str, Any]:
    candidate_id = str(row.get("candidate_id") or "")
    candidate_meta = metadata.get(candidate_id, {})
    annotated = dict(row)
    annotated["run_id"] = run_id
    annotated["source_complexity_class"] = candidate_meta.get("source_complexity_class", "unknown")
    if not annotated.get("mutation_family"):
        annotated["mutation_family"] = candidate_meta.get("mutation_family", "")
    return annotated


def summarize_family_repeatability(observations: list[dict[str, Any]]) -> dict[str, Any]:
    by_candidate: dict[str, list[dict[str, Any]]] = {}
    for row in observations:
        by_candidate.setdefault(str(row.get("candidate_id") or ""), []).append(row)

    candidate_rows: list[dict[str, Any]] = []
    for candidate_id, rows in sorted(by_candidate.items()):
        qualities = [str(row.get("sample_quality") or "") for row in rows]
        true_multi_count = sum(1 for quality in qualities if quality == "multi_turn_useful")
        if true_multi_count == len(rows):
            stability = "stable_true_multi"
        elif true_multi_count:
            stability = "unstable_true_multi"
        else:
            stability = "never_true_multi"
        candidate_rows.append(
            {
                "candidate_id": candidate_id,
                "mutation_family": str(rows[0].get("mutation_family") or ""),
                "source_complexity_class": str(rows[0].get("source_complexity_class") or "unknown"),
                "observation_count": len(rows),
                "true_multi_observation_count": true_multi_count,
                "qualities": qualities,
                "repair_round_counts": [int(row.get("repair_round_count") or 0) for row in rows],
                "stability": stability,
            }
        )

    quality_counts = Counter(str(row.get("sample_quality") or "") for row in observations)
    stability_counts = Counter(str(row.get("stability") or "") for row in candidate_rows)
    family_stability_counts: dict[str, dict[str, int]] = {}
    for row in candidate_rows:
        family = str(row.get("mutation_family") or "")
        stability = str(row.get("stability") or "")
        family_stability_counts.setdefault(family, {})
        family_stability_counts[family][stability] = family_stability_counts[family].get(stability, 0) + 1
    strict = all(
        not row.get("remedy_pack_enabled")
        and not row.get("capability_intervention_pack_enabled")
        and not row.get("broader_change_pack_enabled")
        and not row.get("experience_replay_used")
        and not row.get("planner_experience_injection_used")
        for row in observations
    )
    true_multi_count = int(quality_counts.get("multi_turn_useful", 0))
    promoted_families = [
        family
        for family, counts in sorted(family_stability_counts.items())
        if counts.get("stable_true_multi", 0) >= 1 and counts.get("unstable_true_multi", 0) == 0
    ]
    status = "PASS" if observations and strict and promoted_families else "REVIEW"
    return {
        "version": "v0.22.9",
        "status": status,
        "analysis_scope": "single_point_family_repeatability_gate",
        "observation_count": len(observations),
        "candidate_count": len(candidate_rows),
        "true_multi_observation_count": true_multi_count,
        "true_multi_observation_rate": true_multi_count / len(observations) if observations else 0.0,
        "sample_quality_counts": dict(sorted(quality_counts.items())),
        "candidate_stability_counts": dict(sorted(stability_counts.items())),
        "family_stability_counts": {
            family: dict(sorted(counts.items())) for family, counts in sorted(family_stability_counts.items())
        },
        "promoted_family_candidates": promoted_families,
        "strict_no_auxiliary_packs": strict,
        "candidate_summaries": candidate_rows,
        "conclusion": (
            "single_point_family_repeatability_gate_identified_promotable_families"
            if status == "PASS"
            else "single_point_family_repeatability_gate_needs_review"
        ),
    }


def write_outputs(out_dir: Path, observations: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "repeat_observations.jsonl").open("w", encoding="utf-8") as fh:
        for row in observations:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_family_repeatability(
    *,
    admission_path: Path = DEFAULT_ADMISSION_PATH,
    reference_summary_path: Path = DEFAULT_REFERENCE_SUMMARY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    repeat_count: int = 1,
    max_rounds: int = 8,
    timeout_sec: int = 420,
    limit: int | None = None,
    executor: Callable[[dict[str, Any], Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    admitted_rows = load_jsonl(admission_path)
    cases = build_repair_cases(admitted_rows)
    if limit is not None:
        cases = cases[: max(0, int(limit))]
    selected_case_ids = {str(case.get("candidate_id") or "") for case in cases}
    metadata = _metadata_by_candidate(admitted_rows)
    observations = [
        annotate_observation(row, run_id="v0.22.8_reference", metadata=metadata)
        for row in load_jsonl(reference_summary_path)
        if str(row.get("candidate_id") or "") in selected_case_ids
    ]

    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for repeat_index in range(1, max(0, int(repeat_count)) + 1):
        for case in cases:
            candidate_id = str(case.get("candidate_id") or "")
            raw_path = raw_dir / f"{candidate_id}__repeat_{repeat_index:02d}.json"
            if executor is None:
                payload = run_executor_case(case, raw_path, max_rounds=max_rounds, timeout_sec=timeout_sec)
            else:
                payload = executor(case, raw_path)
                raw_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            observation = summarize_case(case, payload, max_rounds=max_rounds)
            observations.append(
                annotate_observation(observation, run_id=f"v0.22.9_repeat_{repeat_index:02d}", metadata=metadata)
            )
            summary = summarize_family_repeatability(observations)
            write_outputs(out_dir, observations, summary)

    summary = summarize_family_repeatability(observations)
    write_outputs(out_dir, observations, summary)
    return summary
