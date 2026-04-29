from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "semantic_memory_focus_probe_v0_34_6_sem19_run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "reusable_contract_oracle_v0_34_9"


def _success_model_text(row: dict[str, Any]) -> str:
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        success = any(
            isinstance(result, dict)
            and result.get("name") in {"check_model", "simulate_model"}
            and 'resultFile = "/workspace/' in str(result.get("result") or "")
            for result in step.get("tool_results", [])
        )
        if not success:
            continue
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            model_text = str(args.get("model_text") or "")
            if model_text.strip():
                return model_text
    return ""


def _nested_model_blocks(model_text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    lines = model_text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"\s{2,}(?:partial\s+)?model\s+([A-Za-z_][A-Za-z0-9_]*)\b", line)
        if not match:
            index += 1
            continue
        name = match.group(1)
        block_lines = [line]
        index += 1
        while index < len(lines):
            block_lines.append(lines[index])
            if re.match(rf"\s*end\s+{re.escape(name)}\s*;", lines[index]):
                break
            index += 1
        blocks.append((name, "\n".join(block_lines)))
        index += 1
    return blocks


def _flow_equation_count(text: str) -> int:
    return len(re.findall(r"\b[A-Za-z_][A-Za-z0-9_\[\].]*\.i\s*=", text))


def evaluate_reusable_contract_candidate(model_text: str) -> dict[str, Any]:
    nested_blocks = _nested_model_blocks(model_text)
    nested_flow_counts = {name: _flow_equation_count(block) for name, block in nested_blocks}
    nested_flow_total = sum(nested_flow_counts.values())
    total_flow = _flow_equation_count(model_text)
    top_level_flow = max(0, total_flow - nested_flow_total)
    has_replaceable = bool(re.search(r"\breplaceable\s+model\b", model_text))
    contract_oracle_pass = bool(has_replaceable and nested_flow_total > 0 and top_level_flow == 0)
    return {
        "has_replaceable_contract": has_replaceable,
        "nested_model_count": len(nested_blocks),
        "nested_flow_equation_count": nested_flow_total,
        "top_level_flow_equation_count": top_level_flow,
        "nested_flow_counts": dict(sorted(nested_flow_counts.items())),
        "contract_oracle_pass": contract_oracle_pass,
        "reason": (
            "flow_ownership_is_inside_reusable_contract"
            if contract_oracle_pass
            else "flow_ownership_not_cleanly_inside_reusable_contract"
        ),
        "discipline": {
            "oracle_audit_only": True,
            "patch_generated": False,
            "candidate_selected": False,
            "auto_submit": False,
        },
    }


def build_reusable_contract_oracle(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    model_text = _success_model_text(rows[0]) if rows else ""
    evaluation = evaluate_reusable_contract_candidate(model_text) if model_text else {}
    summary = {
        "version": "v0.34.9",
        "status": "PASS" if model_text else "REVIEW",
        "analysis_scope": "reusable_contract_oracle",
        "source_run": run_dir.name,
        "success_candidate_found": bool(model_text),
        "evaluation": evaluation,
        "decision": (
            "success_candidate_fails_reusable_contract_oracle"
            if evaluation and not evaluation.get("contract_oracle_pass")
            else "success_candidate_satisfies_reusable_contract_oracle"
            if evaluation
            else "reusable_contract_oracle_needs_success_candidate"
        ),
        "discipline": {
            "oracle_audit_only": True,
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
