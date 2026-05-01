from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE_DIR = REPO_ROOT / "artifacts" / "replaceable_partial_diagnostic_v0_29_16" / "run_01"
DEFAULT_CONTEXT_DIR = REPO_ROOT / "artifacts" / "modelica_kb_context_probe_v0_29_17" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "modelica_kb_context_probe_v0_29_17" / "summary"


def _rows(path: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("case_id") or ""): row
        for row in load_jsonl(path / "results.jsonl")
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


def build_context_probe_summary(
    *,
    baseline_dir: Path = DEFAULT_BASELINE_DIR,
    context_dir: Path = DEFAULT_CONTEXT_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    baseline = _rows(baseline_dir)
    context = _rows(context_dir)
    case_ids = sorted(set(baseline) | set(context))
    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        base_row = baseline.get(case_id, {})
        context_row = context.get(case_id, {})
        cases.append(
            {
                "case_id": case_id,
                "baseline_verdict": str(base_row.get("final_verdict") or "MISSING"),
                "context_verdict": str(context_row.get("final_verdict") or "MISSING"),
                "baseline_submitted": bool(base_row.get("submitted")),
                "context_submitted": bool(context_row.get("submitted")),
                "baseline_token_used": int(base_row.get("token_used") or 0),
                "context_token_used": int(context_row.get("token_used") or 0),
                "baseline_tool_counts": _tool_counts(base_row),
                "context_tool_counts": _tool_counts(context_row),
            }
        )
    baseline_pass = sum(1 for row in cases if row["baseline_verdict"] == "PASS")
    context_pass = sum(1 for row in cases if row["context_verdict"] == "PASS")
    summary = {
        "version": "v0.29.17",
        "status": "PASS" if cases else "REVIEW",
        "analysis_scope": "modelica_kb_context_probe",
        "case_count": len(cases),
        "baseline_pass_count": baseline_pass,
        "context_pass_count": context_pass,
        "cases": cases,
        "decision": (
            "modelica_context_no_observed_pass_rate_gain"
            if context_pass <= baseline_pass
            else "modelica_context_positive_delta_observed"
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
