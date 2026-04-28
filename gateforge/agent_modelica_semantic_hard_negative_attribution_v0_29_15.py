from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARM_DIRS = {
    "base": REPO_ROOT / "artifacts" / "dyad_ab_v0_29_11" / "arm_a_base_corrected",
    "structural": REPO_ROOT / "artifacts" / "dyad_ab_v0_29_11" / "arm_b_structural",
    "connector": REPO_ROOT / "artifacts" / "dyad_ab_v0_29_11" / "arm_c_connector",
    "semantic": REPO_ROOT / "artifacts" / "dyad_semantic_narrow_v0_29_13" / "semantic_arm",
}
DEFAULT_CASE_IDS = ["sem_06_repl_array_flow", "sem_07_shared_partial_interface"]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_hard_negative_attribution_v0_29_15"


def _rows_by_case(results_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("case_id") or ""): row
        for row in load_jsonl(results_dir / "results.jsonl")
        if row.get("case_id")
    }


def _tool_counts(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name"):
                name = str(call["name"])
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _joined_text(row: dict[str, Any]) -> str:
    return "\n".join(str(step.get("text") or "") for step in row.get("steps", []))


def _labels_for_row(row: dict[str, Any]) -> list[str]:
    text = _joined_text(row).lower()
    labels: list[str] = []
    if int(row.get("token_used") or 0) >= 32000 and not bool(row.get("submitted")):
        labels.append("budget_exhausted_before_submit")
    if "replaceable" in text or "constrainedby" in text:
        labels.append("replaceable_constrainedby_reasoning")
    if "partial" in text:
        labels.append("partial_interface_reasoning")
    if "flow" in text and ("equation" in text or "pin" in text):
        labels.append("flow_equation_reasoning")
    if "circular" in text or "duplicate" in text:
        labels.append("duplicate_or_circular_equation_attempt")
    if "no equation" in text or "underdetermined" in text or "under-determined" in text:
        labels.append("underdetermined_matching_observed")
    return sorted(set(labels))


def summarize_case(case_id: str, by_arm: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    arms: dict[str, Any] = {}
    all_failed = True
    any_submitted = False
    for arm_name, rows in by_arm.items():
        row = rows.get(case_id) or {}
        verdict = str(row.get("final_verdict") or "MISSING")
        all_failed = all_failed and verdict != "PASS"
        any_submitted = any_submitted or bool(row.get("submitted"))
        arms[arm_name] = {
            "final_verdict": verdict,
            "submitted": bool(row.get("submitted")),
            "token_used": int(row.get("token_used") or 0),
            "step_count": int(row.get("step_count") or len(row.get("steps", []))),
            "tool_counts": _tool_counts(row),
            "labels": _labels_for_row(row),
        }
    all_labels = sorted({label for arm in arms.values() for label in arm["labels"]})
    return {
        "case_id": case_id,
        "all_arms_failed": all_failed,
        "any_arm_submitted": any_submitted,
        "arms": arms,
        "labels": all_labels,
        "primary_failure_class": (
            "replaceable_partial_flow_semantics_gap"
            if all_failed and "flow_equation_reasoning" in all_labels and "replaceable_constrainedby_reasoning" in all_labels
            else "budget_or_stopping_failure"
            if all_failed and "budget_exhausted_before_submit" in all_labels
            else "mixed_failure"
        ),
    }


def build_semantic_hard_negative_attribution(
    *,
    arm_dirs: dict[str, Path] | None = None,
    case_ids: list[str] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    selected_arm_dirs = arm_dirs or DEFAULT_ARM_DIRS
    selected_case_ids = case_ids or DEFAULT_CASE_IDS
    by_arm = {arm_name: _rows_by_case(path) for arm_name, path in selected_arm_dirs.items()}
    cases = [summarize_case(case_id, by_arm) for case_id in selected_case_ids]
    all_arms_failed_count = sum(1 for row in cases if row["all_arms_failed"])
    semantic_gap_count = sum(
        1 for row in cases if row["primary_failure_class"] == "replaceable_partial_flow_semantics_gap"
    )
    summary = {
        "version": "v0.29.15",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "semantic_hard_negative_attribution",
        "case_count": len(cases),
        "all_arms_failed_count": all_arms_failed_count,
        "semantic_gap_count": semantic_gap_count,
        "cases": cases,
        "decision": (
            "semantic_hard_negatives_indicate_replaceable_partial_flow_semantics_gap"
            if semantic_gap_count == len(cases)
            else "semantic_hard_negatives_mixed_or_budget_limited"
        ),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
