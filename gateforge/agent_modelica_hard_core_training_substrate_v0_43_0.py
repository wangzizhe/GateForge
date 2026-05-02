from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_repair_report_v0_36_5 import classify_repair_failure


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CALIBRATION = REPO_ROOT / "artifacts" / "difficulty_calibration_v0_42_3" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_training_substrate_v0_43_0"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def hard_negative_case_ids(calibration_summary: dict[str, Any]) -> list[str]:
    case_ids = calibration_summary.get("formal_hard_negative_case_ids")
    if isinstance(case_ids, list):
        return sorted(str(case_id) for case_id in case_ids if str(case_id).strip())
    results = calibration_summary.get("results")
    if not isinstance(results, list):
        return []
    return sorted(
        str(row.get("case_id") or "")
        for row in results
        if str(row.get("difficulty_bucket") or "") == "hard_negative"
    )


def _tool_call_sequence(row: dict[str, Any]) -> list[str]:
    calls: list[str] = []
    for step in row.get("steps") or []:
        for call in step.get("tool_calls") or []:
            name = str(call.get("name") or call.get("tool_name") or "")
            if name:
                calls.append(name)
    return calls


def _tool_result_signal_sequence(row: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    for step in row.get("steps") or []:
        for result in step.get("tool_results") or []:
            text = str(result.get("result") or "")
            lowered = text.lower()
            if "check of" in lowered and "completed successfully" in lowered:
                signals.append("model_check_pass")
            elif "failed to build model" in lowered:
                signals.append("simulation_build_failed")
            elif "translation error" in lowered or "error:" in lowered:
                signals.append("model_check_error")
            elif text.strip():
                signals.append("tool_feedback")
    return signals


def build_training_trajectory_records(
    *,
    hard_case_ids: list[str],
    result_paths: list[Path],
) -> list[dict[str, Any]]:
    hard_cases = set(hard_case_ids)
    records: list[dict[str, Any]] = []
    for path in result_paths:
        for row in load_jsonl(path):
            case_id = str(row.get("case_id") or "")
            if case_id not in hard_cases:
                continue
            if str(row.get("provider_error") or "").strip():
                continue
            if row.get("final_verdict") == "PASS":
                continue
            records.append(
                {
                    "case_id": case_id,
                    "result_path": str(path),
                    "dataset_role": "clean_failed_tool_use_trajectory",
                    "provider": str(row.get("provider") or ""),
                    "tool_profile": str(row.get("tool_profile") or ""),
                    "final_verdict": str(row.get("final_verdict") or ""),
                    "submitted": bool(row.get("submitted")),
                    "step_count": int(row.get("step_count") or len(row.get("steps") or [])),
                    "token_used": int(row.get("token_used") or 0),
                    "tool_call_sequence": _tool_call_sequence(row),
                    "tool_result_signal_sequence": _tool_result_signal_sequence(row),
                    "failure_category": classify_repair_failure(row),
                    "contains_reference_solution": False,
                    "wrapper_repair_added": False,
                }
            )
    return sorted(records, key=lambda record: (record["case_id"], record["result_path"]))


def build_training_substrate_summary(
    *,
    calibration_summary: dict[str, Any],
    result_paths: list[Path],
    version: str = "v0.43.0",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    hard_cases = hard_negative_case_ids(calibration_summary)
    records = build_training_trajectory_records(
        hard_case_ids=hard_cases,
        result_paths=result_paths,
    )
    records_by_case: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        records_by_case.setdefault(str(record["case_id"]), []).append(record)
    repeatable_cases = sorted(
        case_id for case_id, case_records in records_by_case.items() if len(case_records) >= 2
    )
    missing_cases = sorted(case_id for case_id in hard_cases if case_id not in records_by_case)
    summary = {
        "version": version,
        "analysis_scope": "hard_core_training_substrate",
        "status": "PASS" if records and not missing_cases else "REVIEW",
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(records and not missing_cases),
        "hard_negative_case_count": len(hard_cases),
        "trajectory_record_count": len(records),
        "repeatable_case_count": len(repeatable_cases),
        "missing_case_count": len(missing_cases),
        "hard_negative_case_ids": hard_cases,
        "repeatable_case_ids": repeatable_cases,
        "missing_case_ids": missing_cases,
        "result_paths": [str(path) for path in result_paths],
        "dataset_contract": {
            "contains_reference_solution": False,
            "contains_wrapper_repair": False,
            "provider_error_rows_excluded": True,
            "passed_rows_excluded": True,
            "purpose": "failure_trajectory_substrate_before_training",
        },
    }
    return summary, records


def write_training_substrate_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "trajectory_records.jsonl").open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")


def run_training_substrate_build(
    *,
    calibration_path: Path = DEFAULT_CALIBRATION,
    result_paths: list[Path],
    out_dir: Path = DEFAULT_OUT_DIR,
    version: str = "v0.43.0",
) -> dict[str, Any]:
    summary, records = build_training_substrate_summary(
        calibration_summary=load_json(calibration_path),
        result_paths=result_paths,
        version=version,
    )
    write_training_substrate_outputs(out_dir=out_dir, summary=summary, records=records)
    return summary

