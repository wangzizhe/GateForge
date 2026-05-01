from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_residual_obedience_attribution_v0_35_22 import _case_row
from .agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID, _success_evidence_steps

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_delta_portfolio_live_v0_35_26_sem22"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "delta_portfolio_live_attribution_v0_35_26"


def _json_result(text: Any) -> dict[str, Any]:
    try:
        payload = json.loads(str(text or ""))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _portfolio_payloads(row: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict) or call.get("name") != "record_equation_delta_candidate_portfolio":
                continue
            arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            candidates = arguments.get("candidates") if isinstance(arguments.get("candidates"), list) else []
            deltas = []
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                try:
                    deltas.append(int(candidate.get("expected_equation_delta")))
                except (TypeError, ValueError):
                    continue
            try:
                residual_count = int(arguments.get("compiler_named_residual_count"))
            except (TypeError, ValueError):
                residual_count = -1
            payloads.append(
                {
                    "candidate_count": len(candidates),
                    "distinct_delta_count": len(set(deltas)),
                    "expected_equation_deltas": deltas,
                    "has_residual_matching_delta": residual_count in set(deltas),
                }
            )
        for result in step.get("tool_results", []):
            if isinstance(result, dict) and result.get("name") == "record_equation_delta_candidate_portfolio":
                payload = _json_result(result.get("result"))
                if payload:
                    payloads.append(payload)
    return payloads


def _case_summary(row: dict[str, Any]) -> dict[str, Any]:
    base = _case_row(row)
    portfolios = _portfolio_payloads(row)
    base.update(
        {
            "success_evidence_steps": _success_evidence_steps(row),
            "portfolio_call_count": len(portfolios),
            "portfolio_candidate_counts": [payload.get("candidate_count") for payload in portfolios],
            "portfolio_distinct_delta_counts": [payload.get("distinct_delta_count") for payload in portfolios],
            "portfolio_has_residual_matching_delta": any(
                bool(payload.get("has_residual_matching_delta")) for payload in portfolios
            ),
            "portfolio_expected_equation_deltas": [
                payload.get("expected_equation_deltas") for payload in portfolios
            ],
        }
    )
    return base


def build_delta_portfolio_live_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    target_case_id: str = TARGET_CASE_ID,
) -> dict[str, Any]:
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == target_case_id]
    cases = [_case_summary(row) for row in rows]
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    portfolio_used_count = sum(1 for case in cases if case["portfolio_call_count"] > 0)
    residual_matching_count = sum(1 for case in cases if case["portfolio_has_residual_matching_delta"])
    success_candidate_seen_count = sum(1 for case in cases if case["success_evidence_steps"])
    if not rows:
        decision = "delta_portfolio_live_run_missing"
    elif pass_count:
        decision = "delta_portfolio_helped_sem22_pass"
    elif success_candidate_seen_count:
        decision = "delta_portfolio_found_success_candidate_without_submit"
    elif residual_matching_count:
        decision = "delta_portfolio_covered_residual_delta_without_success"
    elif portfolio_used_count:
        decision = "delta_portfolio_used_without_residual_delta_coverage"
    else:
        decision = "delta_portfolio_not_used"
    summary = {
        "version": "v0.35.26",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "delta_portfolio_live_attribution",
        "target_case_id": target_case_id,
        "case_count": len(cases),
        "pass_count": pass_count,
        "portfolio_used_count": portfolio_used_count,
        "residual_matching_count": residual_matching_count,
        "success_candidate_seen_count": success_candidate_seen_count,
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
