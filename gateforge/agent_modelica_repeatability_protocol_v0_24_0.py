from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED_REGISTRY_PATH = REPO_ROOT / "artifacts" / "seed_registry_v0_23_1" / "seed_registry.jsonl"
DEFAULT_TRAJECTORY_PATH = REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2" / "normalized_trajectories.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "repeatability_protocol_v0_24_0"
PROTOCOL_VERSION = "repeatability_protocol_v1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def protocol_definition() -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "levels": ["observation", "run", "candidate", "family"],
        "observation_rule": "one normalized trajectory row is one observation",
        "run_rule": "run_id groups observations produced by one runner invocation or repeat pass",
        "candidate_rule": "candidate_id groups repeated observations for one seed",
        "family_rule": "mutation_family groups candidates with the same mutation intent",
        "candidate_classes": [
            "stable_true_multi",
            "unstable_true_multi",
            "single_repair_then_validate",
            "stable_dead_end",
            "provider_noisy",
            "infra_noisy",
            "mixed_non_success",
            "insufficient_observations",
        ],
        "true_multi_turn_rule": "repair_round_count >= 2 and final_verdict == PASS",
        "executor_attempt_warning": "executor_attempt_count is never a true multi-turn proxy",
    }


def classify_candidate_repeatability(observations: list[dict[str, Any]]) -> str:
    if not observations:
        return "insufficient_observations"
    classes = [str(row.get("trajectory_class") or "") for row in observations]
    provider_failures = [bool(row.get("provider_failure")) for row in observations]
    infra_failures = [bool(row.get("oracle_failure")) for row in observations]
    if all(provider_failures):
        return "provider_noisy"
    if all(infra_failures):
        return "infra_noisy"
    if all(value == "multi_turn_useful" for value in classes):
        return "stable_true_multi"
    if "multi_turn_useful" in classes:
        return "unstable_true_multi"
    if all(value == "single_repair_then_validate" for value in classes):
        return "single_repair_then_validate"
    if all(value == "multi_turn_failed_or_dead_end" for value in classes):
        return "stable_dead_end"
    return "mixed_non_success"


def classify_family_repeatability(candidate_rows: list[dict[str, Any]]) -> str:
    if not candidate_rows:
        return "insufficient_observations"
    classes = [str(row.get("repeatability_class") or "") for row in candidate_rows]
    if all(value == "stable_true_multi" for value in classes):
        return "family_stable_true_multi"
    if classes.count("stable_true_multi") >= 2 and "unstable_true_multi" not in classes:
        return "family_promotable_with_hard_negatives"
    if "stable_true_multi" in classes:
        return "family_seed_only"
    if all(value == "stable_dead_end" for value in classes):
        return "family_stable_dead_end"
    return "family_research_pool"


def build_candidate_rows(
    *,
    seeds: list[dict[str, Any]],
    trajectories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seed_by_id = {str(row.get("seed_id") or row.get("candidate_id") or ""): row for row in seeds}
    observations_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for row in trajectories:
        candidate_id = str(row.get("candidate_id") or row.get("case_id") or "")
        observations_by_candidate.setdefault(candidate_id, []).append(row)

    candidate_ids = sorted(set(seed_by_id) | set(observations_by_candidate))
    candidate_rows: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        seed = seed_by_id.get(candidate_id, {})
        observations = observations_by_candidate.get(candidate_id, [])
        repeatability_class = classify_candidate_repeatability(observations)
        observation_classes = Counter(str(row.get("trajectory_class") or "") for row in observations)
        candidate_rows.append(
            {
                "protocol_version": PROTOCOL_VERSION,
                "candidate_id": candidate_id,
                "seed_id": str(seed.get("seed_id") or candidate_id),
                "mutation_family": str(seed.get("mutation_family") or (observations[0].get("mutation_family") if observations else "unknown")),
                "source_model": str(seed.get("source_model") or "unknown"),
                "source_complexity_class": str(seed.get("source_complexity_class") or "unknown"),
                "observation_count": len(observations),
                "run_ids": sorted({str(row.get("run_id") or "unknown") for row in observations}),
                "trajectory_class_counts": dict(sorted(observation_classes.items())),
                "repair_round_counts": [int(row.get("repair_round_count") or 0) for row in observations],
                "repeatability_class": repeatability_class,
                "registry_policy": str(seed.get("registry_policy") or "unregistered"),
                "routing_allowed": False,
            }
        )
    return candidate_rows


def build_family_rows(candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in candidate_rows:
        by_family.setdefault(str(row.get("mutation_family") or "unknown"), []).append(row)

    family_rows: list[dict[str, Any]] = []
    for family, rows in sorted(by_family.items()):
        class_counts = Counter(str(row.get("repeatability_class") or "") for row in rows)
        family_rows.append(
            {
                "protocol_version": PROTOCOL_VERSION,
                "mutation_family": family,
                "candidate_count": len(rows),
                "observation_count": sum(int(row.get("observation_count") or 0) for row in rows),
                "candidate_repeatability_counts": dict(sorted(class_counts.items())),
                "family_repeatability_class": classify_family_repeatability(rows),
                "routing_allowed": False,
            }
        )
    return family_rows


def build_repeatability_protocol(
    *,
    seed_registry_path: Path = DEFAULT_SEED_REGISTRY_PATH,
    trajectory_path: Path = DEFAULT_TRAJECTORY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    seeds = load_jsonl(seed_registry_path)
    trajectories = load_jsonl(trajectory_path)
    candidate_rows = build_candidate_rows(seeds=seeds, trajectories=trajectories)
    family_rows = build_family_rows(candidate_rows)
    candidate_counts = Counter(str(row.get("repeatability_class") or "") for row in candidate_rows)
    family_counts = Counter(str(row.get("family_repeatability_class") or "") for row in family_rows)
    missing_inputs = []
    if not seeds:
        missing_inputs.append("seed_registry")
    if not trajectories:
        missing_inputs.append("trajectories")
    status = "PASS" if candidate_rows and family_rows and not missing_inputs else "REVIEW"
    summary = {
        "version": "v0.24.0",
        "status": status,
        "analysis_scope": "repeatability_protocol_v1",
        "protocol_version": PROTOCOL_VERSION,
        "missing_inputs": missing_inputs,
        "seed_count": len(seeds),
        "trajectory_count": len(trajectories),
        "candidate_count": len(candidate_rows),
        "family_count": len(family_rows),
        "candidate_repeatability_counts": dict(sorted(candidate_counts.items())),
        "family_repeatability_counts": dict(sorted(family_counts.items())),
        "protocol_definition": protocol_definition(),
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "classification_source": "normalized_trajectories_and_seed_registry",
            "n_turns_is_not_true_multiturn": True,
            "routing_allowed": False,
        },
        "conclusion": (
            "repeatability_protocol_v1_ready_for_unified_repeatability_runner"
            if status == "PASS"
            else "repeatability_protocol_v1_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, candidate_rows=candidate_rows, family_rows=family_rows, summary=summary)
    return summary


def write_outputs(
    *,
    out_dir: Path,
    candidate_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "protocol.json").write_text(
        json.dumps(protocol_definition(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "candidate_repeatability.jsonl").open("w", encoding="utf-8") as fh:
        for row in candidate_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    with (out_dir / "family_repeatability.jsonl").open("w", encoding="utf-8") as fh:
        for row in family_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
