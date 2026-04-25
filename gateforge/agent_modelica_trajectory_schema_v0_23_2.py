from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "resistor_repeat_observations": REPO_ROOT
    / "artifacts"
    / "single_point_repeatability_v0_22_7"
    / "repeat_observations.jsonl",
    "family_repeat_observations": REPO_ROOT
    / "artifacts"
    / "single_point_family_repeatability_v0_22_9"
    / "repeat_observations.jsonl",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2"
TRAJECTORY_SCHEMA_VERSION = "trajectory_schema_v1"
REQUIRED_NORMALIZED_FIELDS = (
    "schema_version",
    "run_id",
    "case_id",
    "candidate_id",
    "repair_round_count",
    "executor_attempt_count",
    "validation_round_count",
    "feedback_sequence",
    "final_verdict",
    "trajectory_class",
)


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


def classify_trajectory(*, repair_round_count: int, final_verdict: str, provider_failure: bool = False) -> str:
    if provider_failure:
        return "provider_failure"
    if final_verdict == "PASS" and repair_round_count >= 2:
        return "multi_turn_useful"
    if final_verdict == "PASS" and repair_round_count == 1:
        return "single_repair_then_validate"
    if repair_round_count >= 2:
        return "multi_turn_failed_or_dead_end"
    return "not_multi_turn"


def normalize_observation(row: dict[str, Any], *, source_artifact: str) -> dict[str, Any]:
    candidate_id = str(row.get("candidate_id") or row.get("case_id") or "")
    repair_round_count = int(row.get("repair_round_count") or 0)
    final_verdict = str(row.get("executor_status") or row.get("final_verdict") or "UNKNOWN")
    feedback_sequence = list(row.get("observed_error_sequence") or row.get("feedback_sequence") or [])
    provider_failure = final_verdict in {"PROVIDER_ERROR", "TIMEOUT", "EMPTY_OUTPUT"}
    trajectory_class = classify_trajectory(
        repair_round_count=repair_round_count,
        final_verdict=final_verdict,
        provider_failure=provider_failure,
    )
    return {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "run_id": str(row.get("run_id") or "unknown"),
        "case_id": candidate_id,
        "candidate_id": candidate_id,
        "model_profile": str(row.get("model_profile") or "unknown"),
        "mutation_family": str(row.get("mutation_family") or "unknown"),
        "source_complexity_class": str(row.get("source_complexity_class") or "unknown"),
        "executor_attempt_count": int(row.get("n_turns") or row.get("executor_attempt_count") or 0),
        "repair_round_count": repair_round_count,
        "validation_round_count": int(row.get("validation_round_count") or 0),
        "feedback_sequence": feedback_sequence,
        "final_verdict": final_verdict,
        "termination": str(row.get("termination") or "unknown"),
        "legacy_sample_quality": str(row.get("sample_quality") or "unknown"),
        "trajectory_class": trajectory_class,
        "true_multi_turn": trajectory_class == "multi_turn_useful",
        "provider_failure": provider_failure,
        "oracle_failure": False,
        "raw_output_ref": None,
        "patch_application_status": "not_recorded_in_legacy_artifact",
        "budget_metadata": {
            "max_rounds": max(int(row.get("n_turns") or 0), repair_round_count),
            "timeout_sec": None,
        },
        "source_artifact": source_artifact,
    }


def validate_normalized_trajectory(row: dict[str, Any]) -> list[str]:
    errors = [f"missing:{field}" for field in REQUIRED_NORMALIZED_FIELDS if field not in row]
    if row.get("true_multi_turn") and int(row.get("repair_round_count") or 0) < 2:
        errors.append("true_multi_turn_requires_repair_round_count_at_least_2")
    if row.get("trajectory_class") == "multi_turn_useful" and row.get("final_verdict") != "PASS":
        errors.append("multi_turn_useful_requires_pass")
    if not isinstance(row.get("feedback_sequence"), list):
        errors.append("feedback_sequence_must_be_list")
    return errors


def schema_definition() -> dict[str, Any]:
    return {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "required_fields": list(REQUIRED_NORMALIZED_FIELDS),
        "true_multi_turn_rule": "repair_round_count >= 2 and final_verdict == PASS",
        "executor_attempts_are_not_repair_rounds": True,
        "trajectory_classes": [
            "multi_turn_useful",
            "single_repair_then_validate",
            "multi_turn_failed_or_dead_end",
            "not_multi_turn",
            "provider_failure",
        ],
    }


def build_trajectory_schema_index(
    *,
    input_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    paths = input_paths or DEFAULT_INPUTS
    normalized_rows: list[dict[str, Any]] = []
    missing_inputs: list[str] = []
    for name, path in paths.items():
        rows = load_jsonl(path)
        if not rows:
            missing_inputs.append(name)
        source_artifact = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
        normalized_rows.extend(normalize_observation(row, source_artifact=source_artifact) for row in rows)

    validation_errors = [
        {"case_id": row.get("case_id"), "run_id": row.get("run_id"), "errors": errors}
        for row in normalized_rows
        if (errors := validate_normalized_trajectory(row))
    ]
    class_counts = Counter(row["trajectory_class"] for row in normalized_rows)
    status = "PASS" if normalized_rows and not missing_inputs and not validation_errors else "REVIEW"
    summary = {
        "version": "v0.23.2",
        "status": status,
        "analysis_scope": "trajectory_schema_v1",
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "trajectory_count": len(normalized_rows),
        "missing_inputs": missing_inputs,
        "validation_error_count": len(validation_errors),
        "trajectory_class_counts": dict(sorted(class_counts.items())),
        "true_multi_turn_count": int(class_counts.get("multi_turn_useful", 0)),
        "schema_definition": schema_definition(),
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "true_multi_turn_source": "repair_round_count_and_final_verdict",
            "n_turns_is_not_true_multiturn": True,
        },
        "conclusion": (
            "trajectory_schema_v1_ready_for_oracle_contract_work"
            if status == "PASS"
            else "trajectory_schema_v1_needs_review"
        ),
    }
    write_outputs(
        out_dir=out_dir,
        normalized_rows=normalized_rows,
        validation_errors=validation_errors,
        summary=summary,
    )
    return summary


def write_outputs(
    *,
    out_dir: Path,
    normalized_rows: list[dict[str, Any]],
    validation_errors: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "schema.json").write_text(
        json.dumps(schema_definition(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "normalized_trajectories.jsonl").open("w", encoding="utf-8") as fh:
        for row in normalized_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    with (out_dir / "validation_errors.jsonl").open("w", encoding="utf-8") as fh:
        for row in validation_errors:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
