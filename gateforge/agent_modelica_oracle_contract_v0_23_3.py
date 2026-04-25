from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAJECTORY_PATH = REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2" / "normalized_trajectories.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "oracle_contract_v0_23_3"
ORACLE_CONTRACT_VERSION = "oracle_contract_v1"
ALLOWED_ORACLE_STATUSES = {
    "model_check_pass",
    "model_check_error",
    "simulation_pass",
    "simulation_error",
    "behavior_pass",
    "behavior_error",
    "infra_error",
    "provider_error",
}


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


def map_feedback_to_oracle_status(feedback: str) -> str:
    value = feedback.strip()
    if value in {"none", "model_check_pass", "check_pass"}:
        return "model_check_pass"
    if value in {"model_check_error", "check_error"}:
        return "model_check_error"
    if value in {"simulation_pass", "simulate_pass"}:
        return "simulation_pass"
    if value in {"simulation_error", "simulate_error"}:
        return "simulation_error"
    if value in {"behavior_pass", "behavior_error", "infra_error", "provider_error"}:
        return value
    return "model_check_error"


def oracle_contract_definition() -> dict[str, Any]:
    return {
        "contract_version": ORACLE_CONTRACT_VERSION,
        "allowed_statuses": sorted(ALLOWED_ORACLE_STATUSES),
        "required_event_fields": [
            "contract_version",
            "run_id",
            "case_id",
            "oracle_type",
            "round_index",
            "status",
            "raw_feedback",
            "repair_hint_allowed",
        ],
        "oracle_role": "validation_only",
        "repair_hint_allowed": False,
        "deterministic_repair_allowed": False,
    }


def normalize_oracle_events(row: dict[str, Any]) -> list[dict[str, Any]]:
    feedback_sequence = row.get("feedback_sequence") or []
    events: list[dict[str, Any]] = []
    for index, feedback in enumerate(feedback_sequence, start=1):
        raw_feedback = str(feedback)
        status = map_feedback_to_oracle_status(raw_feedback)
        events.append(
            {
                "contract_version": ORACLE_CONTRACT_VERSION,
                "run_id": str(row.get("run_id") or "unknown"),
                "case_id": str(row.get("case_id") or ""),
                "candidate_id": str(row.get("candidate_id") or row.get("case_id") or ""),
                "oracle_type": "model_check",
                "round_index": index,
                "status": status,
                "raw_feedback": raw_feedback,
                "repair_hint_allowed": False,
                "deterministic_repair_allowed": False,
                "source_trajectory_class": str(row.get("trajectory_class") or "unknown"),
            }
        )
    return events


def validate_oracle_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in oracle_contract_definition()["required_event_fields"]:
        if field not in event:
            errors.append(f"missing:{field}")
    if event.get("status") not in ALLOWED_ORACLE_STATUSES:
        errors.append("invalid_status")
    if event.get("repair_hint_allowed") is not False:
        errors.append("repair_hint_must_be_false")
    if event.get("deterministic_repair_allowed") is not False:
        errors.append("deterministic_repair_must_be_false")
    return errors


def build_oracle_contract_index(
    *,
    trajectory_path: Path = DEFAULT_TRAJECTORY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    trajectories = load_jsonl(trajectory_path)
    events = [event for row in trajectories for event in normalize_oracle_events(row)]
    validation_errors = [
        {"case_id": event.get("case_id"), "run_id": event.get("run_id"), "round_index": event.get("round_index"), "errors": errors}
        for event in events
        if (errors := validate_oracle_event(event))
    ]
    status_counts = Counter(event["status"] for event in events)
    status = "PASS" if trajectories and events and not validation_errors else "REVIEW"
    summary = {
        "version": "v0.23.3",
        "status": status,
        "analysis_scope": "oracle_contract_v1",
        "contract_version": ORACLE_CONTRACT_VERSION,
        "trajectory_count": len(trajectories),
        "oracle_event_count": len(events),
        "validation_error_count": len(validation_errors),
        "oracle_status_counts": dict(sorted(status_counts.items())),
        "contract_definition": oracle_contract_definition(),
        "discipline": {
            "oracle_role": "validation_only",
            "repair_hint_allowed": False,
            "deterministic_repair_added": False,
            "executor_changes": "none",
        },
        "conclusion": (
            "oracle_contract_v1_ready_for_runner_artifact_contract_work"
            if status == "PASS"
            else "oracle_contract_v1_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, events=events, validation_errors=validation_errors, summary=summary)
    return summary


def write_outputs(
    *,
    out_dir: Path,
    events: list[dict[str, Any]],
    validation_errors: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "contract.json").write_text(
        json.dumps(oracle_contract_definition(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "oracle_events.jsonl").open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
    with (out_dir / "validation_errors.jsonl").open("w", encoding="utf-8") as fh:
        for row in validation_errors:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
