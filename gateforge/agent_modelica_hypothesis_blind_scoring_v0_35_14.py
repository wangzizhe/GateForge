from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_hypothesis_checkpoint_live_v0_35_13"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hypothesis_blind_scoring_v0_35_14"


def _tool_calls(row: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return [
        dict(call.get("arguments") or {})
        for step in row.get("steps", [])
        if isinstance(step, dict)
        for call in step.get("tool_calls", [])
        if isinstance(call, dict) and call.get("name") == name
    ]


def _expected_delta_for_case(case_id: str) -> int:
    if "sem_22" in case_id:
        return 4
    if "sem_23" in case_id:
        return 2
    if "sem_24" in case_id:
        return 2
    return 0


def _target_boundary_ok(case_id: str, target: str) -> bool:
    text = target.lower()
    if "sem_22" in case_id:
        return "probe" in text or "bank" in text
    if "sem_23" in case_id:
        return "probe" in text or "bank" in text
    if "sem_24" in case_id:
        return "probe" in text or "bridgeprobe" in text
    return False


def _strategy_shape(args: dict[str, Any]) -> str:
    strategy = str(args.get("candidate_strategy") or "").lower()
    if re.search(r"\ball\b|all pin|all .*current", strategy):
        return "all_zero_flow"
    if "+" in strategy or "conservation" in strategy or "sum" in strategy:
        return "paired_or_aggregate_flow"
    if "zero" in strategy or re.search(r"\.i\s*=\s*0", strategy):
        return "partial_zero_flow"
    return "other"


def _score_hypothesis(case_id: str, args: dict[str, Any]) -> dict[str, Any]:
    semantic_type = str(args.get("semantic_type") or "")
    target_boundary = str(args.get("target_boundary") or "")
    try:
        expected_delta = int(args.get("expected_equation_delta"))
    except (TypeError, ValueError):
        expected_delta = 0
    semantic_hit = semantic_type == "connector_flow_ownership"
    boundary_hit = _target_boundary_ok(case_id, target_boundary)
    delta_hit = expected_delta == _expected_delta_for_case(case_id)
    shape = _strategy_shape(args)
    over_constraint_risk = shape == "all_zero_flow" or expected_delta > _expected_delta_for_case(case_id)
    return {
        "semantic_type": semantic_type,
        "semantic_hit": semantic_hit,
        "target_boundary": target_boundary,
        "boundary_hit": boundary_hit,
        "expected_equation_delta": expected_delta,
        "expected_delta_hit": delta_hit,
        "strategy_shape": shape,
        "over_constraint_risk": over_constraint_risk,
        "reference_answer_exposed_to_llm": False,
        "blind_score": int(semantic_hit) + int(boundary_hit) + int(delta_hit) - int(over_constraint_risk),
    }


def build_hypothesis_blind_scoring(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row.get("case_id") or "")
        hypotheses = [_score_hypothesis(case_id, args) for args in _tool_calls(row, "record_repair_hypothesis")]
        best_score = max((int(item["blind_score"]) for item in hypotheses), default=0)
        cases.append(
            {
                "case_id": case_id,
                "final_verdict": str(row.get("final_verdict") or ""),
                "hypothesis_count": len(hypotheses),
                "best_blind_score": best_score,
                "semantic_hit_count": sum(1 for item in hypotheses if item["semantic_hit"]),
                "boundary_hit_count": sum(1 for item in hypotheses if item["boundary_hit"]),
                "delta_hit_count": sum(1 for item in hypotheses if item["expected_delta_hit"]),
                "over_constraint_risk_count": sum(1 for item in hypotheses if item["over_constraint_risk"]),
                "hypotheses": hypotheses,
            }
        )
    semantic_hit_cases = sum(1 for case in cases if case["semantic_hit_count"] > 0)
    delta_hit_cases = sum(1 for case in cases if case["delta_hit_count"] > 0)
    over_risk_cases = sum(1 for case in cases if case["over_constraint_risk_count"] > 0)
    if not rows:
        decision = "hypothesis_blind_scoring_missing_run"
    elif semantic_hit_cases and delta_hit_cases == 0:
        decision = "hypotheses_hit_semantic_class_but_miss_repair_granularity"
    elif over_risk_cases:
        decision = "hypotheses_show_overconstraint_bias"
    else:
        decision = "hypothesis_quality_unclear"
    summary = {
        "version": "v0.35.14",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "hypothesis_blind_scoring",
        "case_count": len(cases),
        "semantic_hit_cases": semantic_hit_cases,
        "delta_hit_cases": delta_hit_cases,
        "over_constraint_risk_cases": over_risk_cases,
        "cases": cases,
        "decision": decision,
        "discipline": {
            "reference_answer_exposed_to_llm": False,
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
