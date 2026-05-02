from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECORDS = REPO_ROOT / "artifacts" / "hard_core_training_substrate_v0_43_0" / "trajectory_records.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "training_substrate_quality_audit_v0_43_1"


def classify_training_record_quality(record: dict[str, Any]) -> str:
    if str(record.get("failure_category") or "") != "no_final_submission":
        return "non_submit_failure"
    signals = [str(signal) for signal in record.get("tool_result_signal_sequence") or []]
    calls = [str(call) for call in record.get("tool_call_sequence") or []]
    if "simulate_model" in calls:
        return "no_submit_after_simulation_probe"
    if "model_check_pass" in signals:
        return "no_submit_after_model_check_pass"
    return "no_submit_without_positive_validation_signal"


def build_training_substrate_quality_audit(
    records: list[dict[str, Any]],
    *,
    version: str = "v0.43.1",
) -> dict[str, Any]:
    quality_counts: dict[str, int] = {}
    case_quality: dict[str, set[str]] = {}
    for record in records:
        quality = classify_training_record_quality(record)
        quality_counts[quality] = quality_counts.get(quality, 0) + 1
        case_id = str(record.get("case_id") or "")
        if case_id:
            case_quality.setdefault(case_id, set()).add(quality)

    all_no_submit = bool(records) and all(
        str(record.get("failure_category") or "") == "no_final_submission" for record in records
    )
    no_submit_after_positive_validation = quality_counts.get("no_submit_after_model_check_pass", 0) + quality_counts.get(
        "no_submit_after_simulation_probe", 0
    )
    return {
        "version": version,
        "analysis_scope": "training_substrate_quality_audit",
        "status": "PASS" if records else "REVIEW",
        "record_count": len(records),
        "case_count": len(case_quality),
        "quality_counts": dict(sorted(quality_counts.items())),
        "case_quality": {case_id: sorted(values) for case_id, values in sorted(case_quality.items())},
        "all_failures_are_no_final_submission": all_no_submit,
        "no_submit_after_positive_validation_count": no_submit_after_positive_validation,
        "training_readiness": (
            "submit_decision_dataset_ready"
            if all_no_submit and no_submit_after_positive_validation == len(records)
            else "needs_manual_review_before_training"
        ),
        "scope_note": (
            "These records should not be described as pure Modelica semantic failures without trajectory review. "
            "They are primarily clean failed tool-use trajectories where the Agent did not submit a final model."
        ),
    }


def write_training_substrate_quality_audit_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_training_substrate_quality_audit(
    *,
    records_path: Path = DEFAULT_RECORDS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_training_substrate_quality_audit(load_jsonl(records_path))
    write_training_substrate_quality_audit_outputs(out_dir=out_dir, summary=summary)
    return summary

