from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "resistor_repeatability": REPO_ROOT / "artifacts" / "single_point_repeatability_v0_22_7" / "summary.json",
    "family_repeatability": REPO_ROOT / "artifacts" / "single_point_family_repeatability_v0_22_9" / "summary.json",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "seed_registry_v0_23_1"
PROMOTED_FAMILY_PROTOTYPES = {
    "single_point_resistor_observability_refactor",
    "single_point_capacitor_observability_refactor",
}
SEED_ONLY_FAMILIES = {
    "single_point_sensor_output_abstraction_refactor",
    "single_point_source_parameterization_refactor",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _source_model_from_candidate_id(candidate_id: str) -> str:
    parts = candidate_id.split("_")
    return parts[-1] if parts else "unknown"


def _observed_quality(row: dict[str, Any]) -> str:
    qualities = row.get("qualities")
    if isinstance(qualities, list) and qualities:
        if all(str(value) == "multi_turn_useful" for value in qualities):
            return "multi_turn_useful"
        if "multi_turn_useful" in {str(value) for value in qualities}:
            return "mixed_with_true_multi"
        if "dead_end_hard" in {str(value) for value in qualities}:
            return "dead_end_hard"
        return str(qualities[-1])
    return "unknown"


def classify_seed_policy(*, mutation_family: str, stability: str) -> str:
    if stability == "stable_true_multi" and mutation_family in PROMOTED_FAMILY_PROTOTYPES:
        return "benchmark_positive_candidate"
    if stability == "stable_true_multi" and mutation_family in SEED_ONLY_FAMILIES:
        return "seed_only_positive_candidate"
    if stability == "unstable_true_multi":
        return "research_unstable_candidate"
    if stability == "never_true_multi":
        return "hard_negative_candidate"
    return "research_review_candidate"


def normalize_candidate_summary(
    row: dict[str, Any],
    *,
    source_artifact: str,
    default_family: str,
) -> dict[str, Any]:
    candidate_id = str(row.get("candidate_id") or "")
    mutation_family = str(row.get("mutation_family") or default_family)
    stability = str(row.get("stability") or "unknown")
    policy = classify_seed_policy(mutation_family=mutation_family, stability=stability)
    return {
        "seed_id": candidate_id,
        "candidate_id": candidate_id,
        "source_model": _source_model_from_candidate_id(candidate_id),
        "mutation_family": mutation_family,
        "mutation_intent": mutation_family,
        "failure_type": "ET03",
        "source_complexity_class": str(row.get("source_complexity_class") or "unknown"),
        "omc_admission_status": "admitted_via_source_artifact",
        "live_screening_status": "screened",
        "repeatability_class": stability,
        "true_multi_observation_count": int(row.get("true_multi_observation_count") or 0),
        "observation_count": int(row.get("observation_count") or 0),
        "repair_round_counts": list(row.get("repair_round_counts") or []),
        "observed_quality": _observed_quality(row),
        "registry_policy": policy,
        "public_status": "public_artifact_reference_only",
        "artifact_references": [source_artifact],
        "routing_allowed": False,
    }


def build_seed_registry(
    *,
    input_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    paths = input_paths or DEFAULT_INPUTS
    resistor = load_json(paths["resistor_repeatability"])
    family = load_json(paths["family_repeatability"])
    missing_inputs = [name for name, payload in (("resistor_repeatability", resistor), ("family_repeatability", family)) if not payload]

    seed_rows: list[dict[str, Any]] = []
    for row in resistor.get("candidate_summaries") or []:
        if isinstance(row, dict):
            seed_rows.append(
                normalize_candidate_summary(
                    row,
                    source_artifact=str(paths["resistor_repeatability"].relative_to(REPO_ROOT))
                    if paths["resistor_repeatability"].is_relative_to(REPO_ROOT)
                    else str(paths["resistor_repeatability"]),
                    default_family="single_point_resistor_observability_refactor",
                )
            )
    for row in family.get("candidate_summaries") or []:
        if isinstance(row, dict):
            seed_rows.append(
                normalize_candidate_summary(
                    row,
                    source_artifact=str(paths["family_repeatability"].relative_to(REPO_ROOT))
                    if paths["family_repeatability"].is_relative_to(REPO_ROOT)
                    else str(paths["family_repeatability"]),
                    default_family="unknown",
                )
            )

    duplicate_seed_ids = sorted(
        seed_id for seed_id, count in Counter(row["seed_id"] for row in seed_rows).items() if count > 1
    )
    policy_counts = Counter(row["registry_policy"] for row in seed_rows)
    family_counts = Counter(row["mutation_family"] for row in seed_rows)
    repeatability_counts = Counter(row["repeatability_class"] for row in seed_rows)
    status = "PASS" if seed_rows and not missing_inputs and not duplicate_seed_ids else "REVIEW"
    summary = {
        "version": "v0.23.1",
        "status": status,
        "analysis_scope": "seed_registry_v1",
        "seed_count": len(seed_rows),
        "missing_inputs": missing_inputs,
        "duplicate_seed_ids": duplicate_seed_ids,
        "registry_policy_counts": dict(sorted(policy_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "repeatability_class_counts": dict(sorted(repeatability_counts.items())),
        "promoted_family_prototypes": sorted(PROMOTED_FAMILY_PROTOTYPES),
        "seed_only_families": sorted(SEED_ONLY_FAMILIES),
        "discipline": {
            "routing_allowed": False,
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "registry_role": "benchmark_asset_tracking_only",
        },
        "conclusion": (
            "seed_registry_v1_ready_for_trajectory_schema_work"
            if status == "PASS"
            else "seed_registry_v1_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, seed_rows=seed_rows, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, seed_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "seed_registry.jsonl").open("w", encoding="utf-8") as fh:
        for row in sorted(seed_rows, key=lambda item: item["seed_id"]):
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
