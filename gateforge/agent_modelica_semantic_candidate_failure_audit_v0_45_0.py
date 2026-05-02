from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CALIBRATION = REPO_ROOT / "artifacts" / "difficulty_calibration_v0_42_3" / "summary.json"
DEFAULT_SIGNAL_AUDIT = REPO_ROOT / "artifacts" / "submit_decision_signal_audit_v0_43_2" / "summary.json"
DEFAULT_SUBSTRATE = REPO_ROOT / "artifacts" / "hard_core_training_substrate_v0_43_0" / "trajectory_records.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_candidate_failure_audit_v0_45_0"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def semantic_failure_case_ids(
    *,
    calibration_summary: dict[str, Any],
    signal_audit_summary: dict[str, Any],
) -> list[str]:
    hard = {str(case_id) for case_id in calibration_summary.get("formal_hard_negative_case_ids") or []}
    submit_slice = {str(case_id) for case_id in signal_audit_summary.get("cases_with_successful_omc_evidence") or []}
    return sorted(case_id for case_id in hard - submit_slice if case_id)


def _row_for_record(record: dict[str, Any]) -> dict[str, Any]:
    result_path = Path(str(record.get("result_path") or ""))
    case_id = str(record.get("case_id") or "")
    for row in load_jsonl(result_path):
        if str(row.get("case_id") or "") == case_id and row.get("final_verdict") != "PASS" and not row.get("provider_error"):
            return row
    return {}


def _step_texts(row: dict[str, Any]) -> list[str]:
    return [str(step.get("text") or "") for step in row.get("steps") or []]


def _tool_result_texts(row: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for step in row.get("steps") or []:
        for result in step.get("tool_results") or []:
            text = str(result.get("result") or "")
            if text:
                texts.append(text)
    return texts


def _tool_call_models(row: dict[str, Any]) -> list[str]:
    models: list[str] = []
    for step in row.get("steps") or []:
        for call in step.get("tool_calls") or []:
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            model_text = str(args.get("model_text") or "")
            if model_text:
                models.append(model_text)
    return models


def _distinct_candidate_count(row: dict[str, Any]) -> int:
    return len({re.sub(r"\s+", " ", model).strip() for model in _tool_call_models(row) if model.strip()})


def _last_omc_signal(row: dict[str, Any]) -> str:
    for text in reversed(_tool_result_texts(row)):
        lower = text.lower()
        if 'resultfile = "/workspace/' in text:
            return "successful_omc_evidence"
        if 'resultfile = ""' in lower:
            return "empty_simulation_result"
        if "failed to build model" in lower:
            return "simulation_build_failed"
        if "too many equations" in lower or "over-determined" in lower:
            return "over_determined"
        if "too few equations" in lower or "under-determined" in lower:
            return "under_determined"
        if "index reduction" in lower:
            return "index_reduction_failed"
        if "structurally singular" in lower or "singular" in lower:
            return "structural_singularity"
        if "check of" in lower and "completed successfully" in lower:
            return "check_model_only_pass"
    return "no_omc_signal"


def _belief_markers(row: dict[str, Any]) -> list[str]:
    text = "\n".join(_step_texts(row)).lower()
    markers: list[str] = []
    patterns = {
        "compiler_limitation_claim": ("compiler can't", "compiler cannot", "known issue", "matching algorithm"),
        "symmetry_overcorrection": ("symmetry", "symmetric", "all pins", "both"),
        "flow_current_guessing": ("current", "flow", ".i", "kcl"),
        "interface_contract_uncertainty": ("constrainedby", "partial", "base", "contract", "replaceable"),
        "keeps_searching_after_progress": ("let me try", "different approach", "another approach"),
    }
    for marker, terms in patterns.items():
        if any(term in text for term in terms):
            markers.append(marker)
    return markers


def classify_candidate_failure_mode(row: dict[str, Any]) -> str:
    markers = set(_belief_markers(row))
    last_signal = _last_omc_signal(row)
    if "compiler_limitation_claim" in markers:
        return "compiler_limitation_or_matching_algorithm_belief"
    if "interface_contract_uncertainty" in markers and "flow_current_guessing" in markers:
        return "interface_contract_flow_ownership_confusion"
    if "symmetry_overcorrection" in markers and "flow_current_guessing" in markers:
        return "symmetric_flow_overcorrection"
    if last_signal in {"under_determined", "over_determined", "structural_singularity", "index_reduction_failed"}:
        return "persistent_structural_residual"
    return "unclassified_candidate_generation_failure"


def audit_semantic_candidate_failure_records(
    *,
    semantic_case_ids: list[str],
    substrate_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    wanted = set(semantic_case_ids)
    rows: list[dict[str, Any]] = []
    for record in substrate_records:
        case_id = str(record.get("case_id") or "")
        if case_id not in wanted:
            continue
        row = _row_for_record(record)
        if not row:
            continue
        rows.append(
            {
                "case_id": case_id,
                "result_path": str(record.get("result_path") or ""),
                "step_count": int(row.get("step_count") or len(row.get("steps") or [])),
                "distinct_candidate_count": _distinct_candidate_count(row),
                "last_omc_signal": _last_omc_signal(row),
                "belief_markers": _belief_markers(row),
                "failure_mode": classify_candidate_failure_mode(row),
                "submitted": bool(row.get("submitted")),
                "final_verdict": str(row.get("final_verdict") or ""),
            }
        )
    return sorted(rows, key=lambda item: (item["case_id"], item["result_path"]))


def build_semantic_candidate_failure_audit(
    *,
    calibration_summary: dict[str, Any],
    signal_audit_summary: dict[str, Any],
    substrate_records: list[dict[str, Any]],
    version: str = "v0.45.0",
) -> dict[str, Any]:
    semantic_cases = semantic_failure_case_ids(
        calibration_summary=calibration_summary,
        signal_audit_summary=signal_audit_summary,
    )
    rows = audit_semantic_candidate_failure_records(
        semantic_case_ids=semantic_cases,
        substrate_records=substrate_records,
    )
    mode_counts: dict[str, int] = {}
    signal_counts: dict[str, int] = {}
    for row in rows:
        mode = str(row["failure_mode"])
        signal = str(row["last_omc_signal"])
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        signal_counts[signal] = signal_counts.get(signal, 0) + 1
    return {
        "version": version,
        "analysis_scope": "semantic_candidate_failure_audit",
        "status": "PASS" if rows else "REVIEW",
        "semantic_case_count": len(semantic_cases),
        "trajectory_record_count": len(rows),
        "semantic_case_ids": semantic_cases,
        "failure_mode_counts": dict(sorted(mode_counts.items())),
        "last_omc_signal_counts": dict(sorted(signal_counts.items())),
        "results": rows,
        "decision": "study_candidate_generation_failure_modes",
        "scope_note": (
            "This audit excludes the submit-decision slice with successful OMC evidence. It describes candidate "
            "generation/search failures only; it does not generate patches, select candidates, or submit."
        ),
    }


def write_semantic_candidate_failure_audit_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_semantic_candidate_failure_audit(
    *,
    calibration_path: Path = DEFAULT_CALIBRATION,
    signal_audit_path: Path = DEFAULT_SIGNAL_AUDIT,
    substrate_path: Path = DEFAULT_SUBSTRATE,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_semantic_candidate_failure_audit(
        calibration_summary=load_json(calibration_path),
        signal_audit_summary=load_json(signal_audit_path),
        substrate_records=load_jsonl(substrate_path),
    )
    write_semantic_candidate_failure_audit_outputs(out_dir=out_dir, summary=summary)
    return summary

