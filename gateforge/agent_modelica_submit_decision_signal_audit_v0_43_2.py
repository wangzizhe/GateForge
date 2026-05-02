from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECORDS = REPO_ROOT / "artifacts" / "hard_core_training_substrate_v0_43_0" / "trajectory_records.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "submit_decision_signal_audit_v0_43_2"


def _row_for_record(record: dict[str, Any]) -> dict[str, Any]:
    result_path = Path(str(record.get("result_path") or ""))
    case_id = str(record.get("case_id") or "")
    for row in load_jsonl(result_path):
        if str(row.get("case_id") or "") == case_id and row.get("final_verdict") != "PASS" and not row.get("provider_error"):
            return row
    return {}


def _tool_result_texts(row: dict[str, Any]) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    for step in row.get("steps") or []:
        for result in step.get("tool_results") or []:
            name = str(result.get("name") or "")
            text = str(result.get("result") or "")
            if name and text:
                texts.append((name, text))
    return texts


def has_successful_omc_evidence(row: dict[str, Any]) -> bool:
    return any('resultFile = "/workspace/' in text for name, text in _tool_result_texts(row) if name in {"check_model", "simulate_model"})


def has_empty_resultfile(row: dict[str, Any]) -> bool:
    return any('resultFile = ""' in text for name, text in _tool_result_texts(row) if name in {"check_model", "simulate_model"})


def build_submit_decision_signal_audit(
    records: list[dict[str, Any]],
    *,
    version: str = "v0.43.2",
) -> dict[str, Any]:
    case_rows: dict[str, list[dict[str, Any]]] = {}
    audited_records: list[dict[str, Any]] = []
    for record in records:
        row = _row_for_record(record)
        has_success = has_successful_omc_evidence(row)
        has_empty = has_empty_resultfile(row)
        audited = {
            "case_id": str(record.get("case_id") or ""),
            "result_path": str(record.get("result_path") or ""),
            "failure_category": str(record.get("failure_category") or ""),
            "submitted": bool(record.get("submitted")),
            "tool_call_sequence": list(record.get("tool_call_sequence") or []),
            "has_successful_omc_evidence": has_success,
            "has_empty_resultfile": has_empty,
        }
        audited_records.append(audited)
        case_rows.setdefault(audited["case_id"], []).append(audited)

    success_records = [row for row in audited_records if row["has_successful_omc_evidence"]]
    empty_records = [row for row in audited_records if row["has_empty_resultfile"]]
    all_no_submit = all(not bool(row["submitted"]) for row in audited_records) if audited_records else False
    cases_with_success = sorted(
        case_id for case_id, rows in case_rows.items() if any(row["has_successful_omc_evidence"] for row in rows)
    )
    cases_without_success = sorted(
        case_id for case_id, rows in case_rows.items() if not any(row["has_successful_omc_evidence"] for row in rows)
    )
    return {
        "version": version,
        "analysis_scope": "submit_decision_signal_audit",
        "status": "PASS" if audited_records else "REVIEW",
        "record_count": len(audited_records),
        "case_count": len(case_rows),
        "all_records_no_submit": all_no_submit,
        "successful_omc_evidence_record_count": len(success_records),
        "empty_resultfile_record_count": len(empty_records),
        "cases_with_successful_omc_evidence": cases_with_success,
        "cases_without_successful_omc_evidence": cases_without_success,
        "audited_records": audited_records,
        "decision": (
            "run_submit_checkpoint_ablation"
            if success_records and all_no_submit
            else "separate_semantic_failure_from_submit_failure"
        ),
        "scope_note": (
            "Successful OMC evidence is defined by the same visible signal used by the checkpoint harness: "
            "a non-empty simulation resultFile in check_model or simulate_model output. The audit is descriptive "
            "and does not submit, select, or repair candidates."
        ),
    }


def write_submit_decision_signal_audit_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_submit_decision_signal_audit(
    *,
    records_path: Path = DEFAULT_RECORDS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_submit_decision_signal_audit(load_jsonl(records_path))
    write_submit_decision_signal_audit_outputs(out_dir=out_dir, summary=summary)
    return summary

