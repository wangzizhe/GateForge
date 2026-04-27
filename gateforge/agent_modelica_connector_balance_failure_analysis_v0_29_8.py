from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_RESULTS = REPO_ROOT / "artifacts" / "singleroot2_structural_baseline_v0_29_6" / "results.jsonl"
DEFAULT_STRUCTURAL_RESULTS = REPO_ROOT / "artifacts" / "singleroot2_structural_tools_v0_29_7" / "results.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_balance_failure_analysis_v0_29_8"
DEFAULT_CASE_ID = "singleroot2_03_connector_balance_migration"

EQUATION_COUNT_RE = re.compile(r"has\s+(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)", re.IGNORECASE)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def select_case(rows: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    for row in rows:
        if row.get("case_id") == case_id:
            return row
    return {}


def _tool_result_text(step: dict[str, Any]) -> str:
    parts: list[str] = []
    for result in step.get("tool_results", []):
        if isinstance(result, dict):
            parts.append(str(result.get("result") or ""))
    return "\n".join(parts)


def _called_model_texts(row: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            arguments = call.get("arguments")
            if isinstance(arguments, dict) and isinstance(arguments.get("model_text"), str):
                texts.append(arguments["model_text"])
    return texts


def summarize_tool_usage(row: dict[str, Any]) -> dict[str, Any]:
    sequence: list[str] = []
    counts: dict[str, int] = {}
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            name = str(call.get("name") or "")
            if not name:
                continue
            sequence.append(name)
            counts[name] = counts.get(name, 0) + 1
    return {
        "sequence": sequence,
        "counts": dict(sorted(counts.items())),
        "unique_tools": sorted(counts),
        "structural_tool_calls": sum(
            count for name, count in counts.items() if name not in {"check_model", "simulate_model", "submit_final"}
        ),
    }


def extract_equation_variable_counts(row: dict[str, Any]) -> list[dict[str, int | str]]:
    counts: list[dict[str, int | str]] = []
    for step in row.get("steps", []):
        text = _tool_result_text(step)
        for match in EQUATION_COUNT_RE.finditer(text):
            equations = int(match.group(1))
            variables = int(match.group(2))
            counts.append(
                {
                    "step": int(step.get("step") or 0),
                    "equations": equations,
                    "variables": variables,
                    "balance": "balanced" if equations == variables else "over" if equations > variables else "under",
                }
            )
    return counts


def detect_diagnostic_signals(row: dict[str, Any]) -> dict[str, Any]:
    all_results = "\n".join(_tool_result_text(step) for step in row.get("steps", []))
    lowered = all_results.lower()
    equation_counts = extract_equation_variable_counts(row)
    return {
        "equation_variable_counts": equation_counts,
        "saw_overdetermined_count": any(item["balance"] == "over" for item in equation_counts),
        "saw_underdetermined_count": any(item["balance"] == "under" for item in equation_counts),
        "saw_balanced_count": any(item["balance"] == "balanced" for item in equation_counts),
        "saw_connector_language": "connector" in lowered,
        "saw_failed_build": "failed to build model" in lowered,
        "saw_unmatched_none": "no underdetermined variables found" in lowered,
    }


def classify_patch_patterns(model_texts: list[str]) -> dict[str, Any]:
    patterns = {
        "removed_extra_flow_sensor": False,
        "demoted_extra_flow_sensor_to_plain_real": False,
        "added_extra_potential_sensor": False,
        "removed_adapter_flow_balance_equation": False,
        "attempted_standard_pin_extension": False,
        "retained_direct_voltage_bindings": False,
        "attempted_adapter_connect_to_electrical_network": False,
    }
    for text in model_texts:
        compact = re.sub(r"\s+", "", text)
        if "iSense" not in text:
            patterns["removed_extra_flow_sensor"] = True
        if re.search(r"(?<!flow\s)Real\s+iSense\b", text):
            patterns["demoted_extra_flow_sensor_to_plain_real"] = True
        if re.search(r"\bReal\s+vSense\b", text):
            patterns["added_extra_potential_sensor"] = True
        if "p.i+n.i=0" not in compact:
            patterns["removed_adapter_flow_balance_equation"] = True
        if "Modelica.Electrical.Analog.Interfaces.Pin" in text:
            patterns["attempted_standard_pin_extension"] = True
        if "adapter.p.v=C1.p.v" in compact and "adapter.n.v=C1.n.v" in compact:
            patterns["retained_direct_voltage_bindings"] = True
        if "connect(adapter.p" in text or "connect(adapter.n" in text:
            patterns["attempted_adapter_connect_to_electrical_network"] = True
    active = sorted(name for name, value in patterns.items() if value)
    return {
        **patterns,
        "active_patterns": active,
        "oscillation_detected": len(active) >= 3,
    }


def summarize_arm(row: dict[str, Any]) -> dict[str, Any]:
    model_texts = _called_model_texts(row)
    return {
        "case_id": str(row.get("case_id") or ""),
        "tool_profile": str(row.get("tool_profile") or ""),
        "final_verdict": str(row.get("final_verdict") or "MISSING"),
        "submitted": bool(row.get("submitted")),
        "step_count": int(row.get("step_count") or len(row.get("steps", []))),
        "token_used": int(row.get("token_used") or 0),
        "tool_usage": summarize_tool_usage(row),
        "diagnostic_signals": detect_diagnostic_signals(row),
        "patch_patterns": classify_patch_patterns(model_texts),
    }


def build_connector_balance_failure_analysis(
    *,
    base_row: dict[str, Any],
    structural_row: dict[str, Any],
    case_id: str = DEFAULT_CASE_ID,
) -> dict[str, Any]:
    base = summarize_arm(base_row) if base_row else {"final_verdict": "MISSING"}
    structural = summarize_arm(structural_row) if structural_row else {"final_verdict": "MISSING"}
    both_failed = base.get("final_verdict") != "PASS" and structural.get("final_verdict") != "PASS"
    structural_used_extra_tools = (
        int(structural.get("tool_usage", {}).get("structural_tool_calls", 0))
        if isinstance(structural.get("tool_usage"), dict)
        else 0
    ) > 0
    return {
        "version": "v0.29.8",
        "status": "PASS" if base_row and structural_row else "REVIEW",
        "analysis_scope": "connector_balance_failure_analysis",
        "case_id": case_id,
        "base": base,
        "structural": structural,
        "comparison": {
            "both_arms_failed": both_failed,
            "structural_tools_used": structural_used_extra_tools,
            "pass_delta_for_case": 0 if both_failed else 1 if structural.get("final_verdict") == "PASS" else -1,
            "primary_failure_class": (
                "connector_balance_semantics_gap" if both_failed else "connector_balance_case_not_persistent_failure"
            ),
            "diagnostic_gap": (
                "existing_structural_tools_expose_matching_and_causalization_but_not_connector_balance_semantics"
                if both_failed and structural_used_extra_tools
                else "insufficient_evidence"
            ),
        },
        "decision": (
            "add_diagnostic_only_connector_balance_tool_or_more_connector_semantics_cases"
            if both_failed
            else "case_no_longer_blocks_current_tool_profile"
        ),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
        },
    }


def run_connector_balance_failure_analysis(
    *,
    base_results_path: Path = DEFAULT_BASE_RESULTS,
    structural_results_path: Path = DEFAULT_STRUCTURAL_RESULTS,
    out_dir: Path = DEFAULT_OUT_DIR,
    case_id: str = DEFAULT_CASE_ID,
) -> dict[str, Any]:
    base_row = select_case(load_jsonl(base_results_path), case_id)
    structural_row = select_case(load_jsonl(structural_results_path), case_id)
    summary = build_connector_balance_failure_analysis(
        base_row=base_row,
        structural_row=structural_row,
        case_id=case_id,
    )
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
