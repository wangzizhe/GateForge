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
from gateforge.agent_modelica_single_point_complex_screening_v0_22_6 import build_repair_cases


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADMISSION_PATH = REPO_ROOT / "artifacts" / "single_point_complex_pack_v0_22_6" / "single_point_candidates.jsonl"
DEFAULT_REFERENCE_SUMMARY_PATH = REPO_ROOT / "artifacts" / "single_point_complex_screening_v0_22_6" / "case_summaries.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "single_point_repeatability_v0_22_7"


def load_reference_summaries(path: Path) -> list[dict[str, Any]]:
    return load_jsonl(path)


def _candidate_complexity_map(admitted_rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(row.get("candidate_id") or ""): str(row.get("source_complexity_class") or "unknown")
        for row in admitted_rows
        if row.get("candidate_id")
    }


def annotate_observation(row: dict[str, Any], *, run_id: str, complexity_by_candidate: dict[str, str]) -> dict[str, Any]:
    candidate_id = str(row.get("candidate_id") or "")
    annotated = dict(row)
    annotated["run_id"] = run_id
    annotated["source_complexity_class"] = complexity_by_candidate.get(candidate_id, "unknown")
    return annotated


def summarize_repeatability(observations: list[dict[str, Any]]) -> dict[str, Any]:
    by_candidate: dict[str, list[dict[str, Any]]] = {}
    for row in observations:
        by_candidate.setdefault(str(row.get("candidate_id") or ""), []).append(row)

    candidate_rows: list[dict[str, Any]] = []
    for candidate_id, rows in sorted(by_candidate.items()):
        qualities = [str(row.get("sample_quality") or "") for row in rows]
        statuses = [str(row.get("executor_status") or "") for row in rows]
        repair_rounds = [int(row.get("repair_round_count") or 0) for row in rows]
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
                "source_complexity_class": str(rows[0].get("source_complexity_class") or "unknown"),
                "observation_count": len(rows),
                "true_multi_observation_count": true_multi_count,
                "qualities": qualities,
                "executor_statuses": statuses,
                "repair_round_counts": repair_rounds,
                "stability": stability,
            }
        )

    quality_counts = Counter(str(row.get("sample_quality") or "") for row in observations)
    stability_counts = Counter(str(row.get("stability") or "") for row in candidate_rows)
    complexity_stability_counts: dict[str, dict[str, int]] = {}
    for row in candidate_rows:
        complexity = str(row.get("source_complexity_class") or "unknown")
        stability = str(row.get("stability") or "")
        complexity_stability_counts.setdefault(complexity, {})
        complexity_stability_counts[complexity][stability] = complexity_stability_counts[complexity].get(stability, 0) + 1

    strict_observations = [
        row
        for row in observations
        if not row.get("remedy_pack_enabled")
        and not row.get("capability_intervention_pack_enabled")
        and not row.get("broader_change_pack_enabled")
        and not row.get("experience_replay_used")
        and not row.get("planner_experience_injection_used")
    ]
    strict = len(strict_observations) == len(observations)
    true_multi_count = int(quality_counts.get("multi_turn_useful", 0))
    status = "PASS" if observations and strict and int(stability_counts.get("stable_true_multi", 0)) >= 4 else "REVIEW"
    return {
        "version": "v0.22.7",
        "status": status,
        "analysis_scope": "single_point_complex_repeatability_audit",
        "observation_count": len(observations),
        "candidate_count": len(candidate_rows),
        "true_multi_observation_count": true_multi_count,
        "true_multi_observation_rate": true_multi_count / len(observations) if observations else 0.0,
        "sample_quality_counts": dict(sorted(quality_counts.items())),
        "candidate_stability_counts": dict(sorted(stability_counts.items())),
        "complexity_stability_counts": {
            key: dict(sorted(value.items())) for key, value in sorted(complexity_stability_counts.items())
        },
        "strict_no_auxiliary_packs": strict,
        "candidate_summaries": candidate_rows,
        "conclusion": (
            "single_point_complex_true_multiturn_signal_is_repeatable"
            if status == "PASS"
            else "single_point_complex_true_multiturn_signal_needs_more_review"
        ),
    }


def write_outputs(out_dir: Path, observations: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "repeat_observations.jsonl").open("w", encoding="utf-8") as fh:
        for row in observations:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_single_point_repeatability(
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
    complexity_by_candidate = _candidate_complexity_map(admitted_rows)
    selected_case_ids = {str(case.get("candidate_id") or "") for case in cases}
    observations = [
        annotate_observation(row, run_id="v0.22.6_reference", complexity_by_candidate=complexity_by_candidate)
        for row in load_reference_summaries(reference_summary_path)
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
                annotate_observation(
                    observation,
                    run_id=f"v0.22.7_repeat_{repeat_index:02d}",
                    complexity_by_candidate=complexity_by_candidate,
                )
            )
            summary = summarize_repeatability(observations)
            write_outputs(out_dir, observations, summary)

    summary = summarize_repeatability(observations)
    write_outputs(out_dir, observations, summary)
    return summary
