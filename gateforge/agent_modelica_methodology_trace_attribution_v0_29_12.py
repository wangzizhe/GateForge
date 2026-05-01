from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_DIR = REPO_ROOT / "artifacts" / "methodology_ab_v0_29_11" / "arm_a_base_corrected"
DEFAULT_CONNECTOR_DIR = REPO_ROOT / "artifacts" / "methodology_ab_v0_29_11" / "arm_c_connector"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "methodology_trace_attribution_v0_29_12"
DIAGNOSTIC_TOOLS = {
    "who_defines",
    "who_uses",
    "declared_but_unused",
    "get_unmatched_vars",
    "causalized_form",
    "connector_balance_diagnostic",
}


def _rows_by_case(results_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("case_id") or ""): row
        for row in load_jsonl(results_dir / "results.jsonl")
        if row.get("case_id")
    }


def tool_sequence(row: dict[str, Any]) -> list[str]:
    sequence: list[str] = []
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name"):
                sequence.append(str(call["name"]))
    return sequence


def tool_counts(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in tool_sequence(row):
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _first_texts(row: dict[str, Any], limit: int = 3) -> list[str]:
    texts: list[str] = []
    for step in row.get("steps", [])[:limit]:
        text = str(step.get("text") or "").strip()
        if text:
            texts.append(text[:500])
    return texts


def classify_transition(*, base_row: dict[str, Any], connector_row: dict[str, Any]) -> dict[str, Any]:
    base_verdict = str(base_row.get("final_verdict") or "MISSING")
    connector_verdict = str(connector_row.get("final_verdict") or "MISSING")
    connector_tools = tool_counts(connector_row)
    used_connector_diagnostic = connector_tools.get("connector_balance_diagnostic", 0) > 0
    diagnostic_call_count = sum(count for name, count in connector_tools.items() if name in DIAGNOSTIC_TOOLS)
    token_used = int(connector_row.get("token_used") or 0)
    submitted = bool(connector_row.get("submitted"))
    labels: list[str] = []

    if base_verdict != "PASS" and connector_verdict == "PASS":
        labels.append("connector_positive_delta")
        if used_connector_diagnostic:
            labels.append("connector_diagnostic_used")
        else:
            labels.append("no_connector_diagnostic_used")
        if diagnostic_call_count:
            labels.append("diagnostic_path_changed")
        else:
            labels.append("prompt_or_sampling_path_changed")
    elif base_verdict == "PASS" and connector_verdict != "PASS":
        labels.append("connector_regression")
        if not submitted and token_used >= 32000:
            labels.append("budget_exhausted_before_submit")
        if diagnostic_call_count:
            labels.append("diagnostic_path_overhead_or_misdirection")
        if used_connector_diagnostic:
            labels.append("connector_diagnostic_not_sufficient")
    elif base_verdict == connector_verdict:
        labels.append("no_verdict_delta")
    else:
        labels.append("other_transition")

    if connector_verdict != "PASS" and bool(connector_row.get("submitted")):
        labels.append("submitted_but_failed_final_eval")

    return {
        "case_id": str(connector_row.get("case_id") or base_row.get("case_id") or ""),
        "base_verdict": base_verdict,
        "connector_verdict": connector_verdict,
        "base_submitted": bool(base_row.get("submitted")),
        "connector_submitted": submitted,
        "base_token_used": int(base_row.get("token_used") or 0),
        "connector_token_used": token_used,
        "base_tool_counts": tool_counts(base_row),
        "connector_tool_counts": connector_tools,
        "connector_tool_sequence": tool_sequence(connector_row),
        "used_connector_balance_diagnostic": used_connector_diagnostic,
        "diagnostic_call_count": diagnostic_call_count,
        "labels": labels,
        "base_first_texts": _first_texts(base_row),
        "connector_first_texts": _first_texts(connector_row),
    }


def build_methodology_trace_attribution(
    *,
    base_dir: Path = DEFAULT_BASE_DIR,
    connector_dir: Path = DEFAULT_CONNECTOR_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    base_rows = _rows_by_case(base_dir)
    connector_rows = _rows_by_case(connector_dir)
    case_ids = sorted(set(base_rows) & set(connector_rows))
    changed = [
        classify_transition(base_row=base_rows[case_id], connector_row=connector_rows[case_id])
        for case_id in case_ids
        if str(base_rows[case_id].get("final_verdict") or "") != str(connector_rows[case_id].get("final_verdict") or "")
    ]
    label_counts: dict[str, int] = {}
    for row in changed:
        for label in row["labels"]:
            label_counts[label] = label_counts.get(label, 0) + 1

    positive = [row for row in changed if "connector_positive_delta" in row["labels"]]
    regressions = [row for row in changed if "connector_regression" in row["labels"]]
    direct_connector_tool_positive = [
        row for row in positive if row["used_connector_balance_diagnostic"]
    ]
    summary = {
        "version": "v0.29.12",
        "status": "PASS" if case_ids else "REVIEW",
        "analysis_scope": "methodology_connector_trace_attribution",
        "case_count": len(case_ids),
        "changed_case_count": len(changed),
        "positive_delta_count": len(positive),
        "regression_count": len(regressions),
        "direct_connector_tool_positive_count": len(direct_connector_tool_positive),
        "label_counts": dict(sorted(label_counts.items())),
        "changed_cases": changed,
        "decision": (
            "connector_profile_positive_not_attributable_to_connector_diagnostic"
            if positive and not direct_connector_tool_positive
            else "connector_profile_has_direct_connector_diagnostic_gain"
            if direct_connector_tool_positive
            else "connector_profile_no_positive_cases"
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
