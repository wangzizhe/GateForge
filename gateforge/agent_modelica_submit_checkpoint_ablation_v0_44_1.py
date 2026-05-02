from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_AUDIT = REPO_ROOT / "artifacts" / "submit_decision_signal_audit_v0_43_2" / "summary.json"
DEFAULT_CHECKPOINT_RESULTS = REPO_ROOT / "artifacts" / "submit_checkpoint_ablation_v0_44_0" / "results.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "submit_checkpoint_ablation_summary_v0_44_1"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _has_checkpoint_message(row: dict[str, Any]) -> bool:
    return any(bool(step.get("checkpoint_messages")) for step in row.get("steps") or [])


def _has_checkpoint_guard(row: dict[str, Any]) -> bool:
    return any(bool(step.get("checkpoint_guard_violations")) for step in row.get("steps") or [])


def build_submit_checkpoint_ablation_summary(
    *,
    base_audit: dict[str, Any],
    checkpoint_rows: list[dict[str, Any]],
    version: str = "v0.44.1",
) -> dict[str, Any]:
    target_case_ids = [str(case_id) for case_id in base_audit.get("cases_with_successful_omc_evidence") or []]
    checkpoint_by_case = {str(row.get("case_id") or ""): row for row in checkpoint_rows}
    pass_case_ids = sorted(
        case_id for case_id in target_case_ids if checkpoint_by_case.get(case_id, {}).get("final_verdict") == "PASS"
    )
    submitted_case_ids = sorted(
        case_id for case_id in target_case_ids if bool(checkpoint_by_case.get(case_id, {}).get("submitted"))
    )
    provider_error_case_ids = sorted(
        case_id for case_id in target_case_ids if str(checkpoint_by_case.get(case_id, {}).get("provider_error") or "")
    )
    checkpoint_message_case_ids = sorted(
        case_id for case_id in target_case_ids if _has_checkpoint_message(checkpoint_by_case.get(case_id, {}))
    )
    checkpoint_guard_case_ids = sorted(
        case_id for case_id in target_case_ids if _has_checkpoint_guard(checkpoint_by_case.get(case_id, {}))
    )
    return {
        "version": version,
        "analysis_scope": "submit_checkpoint_ablation_summary",
        "status": "PASS" if target_case_ids else "REVIEW",
        "evidence_role": "formal_experiment",
        "target_case_count": len(target_case_ids),
        "target_case_ids": target_case_ids,
        "checkpoint_pass_count": len(pass_case_ids),
        "checkpoint_submit_count": len(submitted_case_ids),
        "provider_error_count": len(provider_error_case_ids),
        "checkpoint_message_case_ids": checkpoint_message_case_ids,
        "checkpoint_guard_case_ids": checkpoint_guard_case_ids,
        "pass_case_ids": pass_case_ids,
        "submitted_case_ids": submitted_case_ids,
        "provider_error_case_ids": provider_error_case_ids,
        "decision": (
            "submit_checkpoint_promote_for_submit_signal_slice"
            if target_case_ids and len(pass_case_ids) == len(target_case_ids) and not provider_error_case_ids
            else "submit_checkpoint_needs_more_evidence"
        ),
        "scope_note": (
            "This result only applies to cases where the base run already showed successful OMC evidence but did "
            "not submit. It must not be generalized to all hard negatives or described as semantic repair uplift."
        ),
    }


def write_submit_checkpoint_ablation_summary_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_submit_checkpoint_ablation_summary(
    *,
    base_audit_path: Path = DEFAULT_BASE_AUDIT,
    checkpoint_results_path: Path = DEFAULT_CHECKPOINT_RESULTS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_submit_checkpoint_ablation_summary(
        base_audit=load_json(base_audit_path),
        checkpoint_rows=load_jsonl(checkpoint_results_path),
    )
    write_submit_checkpoint_ablation_summary_outputs(out_dir=out_dir, summary=summary)
    return summary

