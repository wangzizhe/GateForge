from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_DIR = REPO_ROOT / "artifacts" / "semantic_strategy_cards_live_probe_v0_33_5"
DEFAULT_MEMORY_DIR = REPO_ROOT / "artifacts" / "semantic_memory_units_live_probe_v0_34_1"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_memory_live_comparison_v0_34_2"


def _rows_by_case(run_dir: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(run_dir / "results.jsonl"):
        case_id = str(row.get("case_id") or "")
        rows[case_id] = {
            "case_id": case_id,
            "final_verdict": str(row.get("final_verdict") or ""),
            "submitted": bool(row.get("submitted")),
            "provider_error": str(row.get("provider_error") or ""),
            "token_used": int(row.get("token_used") or 0),
            "step_count": int(row.get("step_count") or 0),
            "tool_sequence": [
                call.get("name")
                for step in row.get("steps", [])
                if isinstance(step, dict)
                for call in step.get("tool_calls", [])
                if isinstance(call, dict)
            ],
        }
    return rows


def build_semantic_memory_live_comparison(
    *,
    baseline_dir: Path = DEFAULT_BASELINE_DIR,
    memory_dir: Path = DEFAULT_MEMORY_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    baseline = _rows_by_case(baseline_dir)
    memory = _rows_by_case(memory_dir)
    case_ids = sorted(set(baseline) | set(memory))
    paired_rows: list[dict[str, Any]] = []
    improved = 0
    regressed = 0
    unchanged = 0
    for case_id in case_ids:
        base = baseline.get(case_id, {})
        mem = memory.get(case_id, {})
        base_pass = base.get("final_verdict") == "PASS"
        mem_pass = mem.get("final_verdict") == "PASS"
        if mem_pass and not base_pass:
            delta = "improved"
            improved += 1
        elif base_pass and not mem_pass:
            delta = "regressed"
            regressed += 1
        else:
            delta = "unchanged"
            unchanged += 1
        paired_rows.append(
            {
                "case_id": case_id,
                "baseline_verdict": str(base.get("final_verdict") or "MISSING"),
                "memory_verdict": str(mem.get("final_verdict") or "MISSING"),
                "baseline_submitted": bool(base.get("submitted")),
                "memory_submitted": bool(mem.get("submitted")),
                "baseline_provider_error": str(base.get("provider_error") or ""),
                "memory_provider_error": str(mem.get("provider_error") or ""),
                "baseline_token_used": int(base.get("token_used") or 0),
                "memory_token_used": int(mem.get("token_used") or 0),
                "memory_tool_sequence": list(mem.get("tool_sequence") or []),
                "delta": delta,
            }
        )
    pass_count_baseline = sum(1 for row in baseline.values() if row["final_verdict"] == "PASS")
    pass_count_memory = sum(1 for row in memory.values() if row["final_verdict"] == "PASS")
    if improved and not regressed:
        decision = "semantic_memory_units_show_partial_positive_live_signal"
    elif regressed and not improved:
        decision = "semantic_memory_units_regress_live_signal"
    elif improved and regressed:
        decision = "semantic_memory_units_mixed_live_signal"
    else:
        decision = "semantic_memory_units_no_live_delta"
    summary = {
        "version": "v0.34.2",
        "status": "PASS" if case_ids and not any(row["memory_provider_error"] for row in paired_rows) else "REVIEW",
        "analysis_scope": "semantic_memory_live_comparison",
        "baseline_label": "generic_strategy_cards_v0_33_5",
        "memory_label": "semantic_memory_units_v0_34_1",
        "case_count": len(case_ids),
        "baseline_pass_count": pass_count_baseline,
        "memory_pass_count": pass_count_memory,
        "improved_count": improved,
        "regressed_count": regressed,
        "unchanged_count": unchanged,
        "paired_rows": paired_rows,
        "decision": decision,
        "discipline": {
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
