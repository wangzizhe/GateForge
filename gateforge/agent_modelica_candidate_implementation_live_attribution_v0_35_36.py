from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_delta_portfolio_live_attribution_v0_35_26 import _case_summary
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "sem19_candidate_implementation_live_v0_35_36"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_implementation_live_attribution_v0_35_36"


def _implementation_payloads(row: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for result in step.get("tool_results", []):
            if not isinstance(result, dict) or result.get("name") != "candidate_implementation_consistency_check":
                continue
            try:
                payload = json.loads(str(result.get("result") or ""))
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


def _case_implementation_summary(row: dict[str, Any]) -> dict[str, Any]:
    case = _case_summary(row)
    payloads = _implementation_payloads(row)
    case.update(
        {
            "implementation_check_count": len(payloads),
            "implementation_match_count": sum(
                1 for payload in payloads if payload.get("implementation_matches_expected_delta")
            ),
            "implementation_mismatch_count": sum(
                1 for payload in payloads if payload.get("implementation_matches_expected_delta") is False
            ),
            "implemented_zero_flow_equation_counts": [
                payload.get("implemented_zero_flow_equation_count") for payload in payloads
            ],
            "implementation_expected_deltas": [payload.get("expected_equation_delta") for payload in payloads],
        }
    )
    return case


def build_candidate_implementation_live_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases = [_case_implementation_summary(row) for row in rows]
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    mismatch_count = sum(1 for case in cases if case["implementation_mismatch_count"] > 0)
    match_count = sum(1 for case in cases if case["implementation_match_count"] > 0)
    if not rows:
        decision = "candidate_implementation_live_run_missing"
    elif pass_count:
        decision = "candidate_implementation_check_helped_pass"
    elif mismatch_count:
        decision = "implementation_mismatch_detected_without_recovery"
    elif match_count:
        decision = "implementation_matched_expected_delta_without_success"
    else:
        decision = "candidate_implementation_check_not_used"
    summary = {
        "version": "v0.35.36",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "candidate_implementation_live_attribution",
        "case_count": len(cases),
        "pass_count": pass_count,
        "implementation_mismatch_case_count": mismatch_count,
        "implementation_match_case_count": match_count,
        "cases": cases,
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
