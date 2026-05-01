from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_hypothesis_blind_scoring_v0_35_14 import _score_hypothesis, _tool_calls

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_minimal_contract_live_v0_35_15"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "minimal_contract_attribution_v0_35_15"


def _zero_flow_equations(model_text: str) -> list[str]:
    rows: list[str] = []
    for raw in str(model_text or "").split(";"):
        row = " ".join(raw.strip().split())
        if re.search(r"(?:^|\.)[A-Za-z_][A-Za-z0-9_\[\]]*\.i\s*=\s*0(?:\.0)?$", row):
            rows.append(row)
    return rows


def _candidate_success_steps(row: dict[str, Any]) -> list[int]:
    steps: list[int] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for result in step.get("tool_results", []):
            if 'resultFile = "/workspace/' in str(result.get("result") or ""):
                steps.append(int(step.get("step") or 0))
                break
    return steps


def _case_row(row: dict[str, Any]) -> dict[str, Any]:
    case_id = str(row.get("case_id") or "")
    hypotheses = [_score_hypothesis(case_id, args) for args in _tool_calls(row, "record_repair_hypothesis")]
    final_model = str(row.get("final_model_text") or "")
    zero_flow_equations = _zero_flow_equations(final_model)
    submitted = bool(row.get("submitted"))
    final_pass = str(row.get("final_verdict") or "") == "PASS"
    return {
        "case_id": case_id,
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": submitted,
        "success_evidence_steps": _candidate_success_steps(row),
        "hypothesis_count": len(hypotheses),
        "hypotheses": hypotheses,
        "zero_flow_equation_count": len(zero_flow_equations),
        "zero_flow_equation_examples": zero_flow_equations[:8],
        "pass_with_minimal_implemented_contract": final_pass and len(zero_flow_equations) in {2, 4},
        "hypothesis_overconstraint_risk_count": sum(1 for item in hypotheses if item["over_constraint_risk"]),
    }


def build_minimal_contract_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases = [_case_row(row) for row in rows]
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    success_candidate_seen_count = sum(1 for case in cases if case["success_evidence_steps"])
    minimal_pass_count = sum(1 for case in cases if case["pass_with_minimal_implemented_contract"])
    overconstraint_hypothesis_cases = sum(1 for case in cases if case["hypothesis_overconstraint_risk_count"] > 0)
    if not rows:
        decision = "minimal_contract_live_run_missing"
    elif minimal_pass_count:
        decision = "minimal_contract_guidance_improves_implemented_candidate_granularity"
    elif overconstraint_hypothesis_cases:
        decision = "minimal_contract_guidance_still_overstates_hypothesis"
    else:
        decision = "minimal_contract_effect_unclear"
    summary = {
        "version": "v0.35.15",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "minimal_contract_attribution",
        "case_count": len(cases),
        "pass_count": pass_count,
        "success_candidate_seen_count": success_candidate_seen_count,
        "minimal_pass_count": minimal_pass_count,
        "overconstraint_hypothesis_cases": overconstraint_hypothesis_cases,
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
