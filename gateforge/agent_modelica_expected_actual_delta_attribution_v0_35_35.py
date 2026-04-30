from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_delta_portfolio_live_attribution_v0_35_26 import _case_summary
from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "sem19_delta_execution_live_v0_35_34",
    REPO_ROOT / "artifacts" / "arrayed_flow_candidate_preference_live_v0_35_31",
]
DEFAULT_TARGET_CASE_IDS = [
    "sem_19_arrayed_shared_probe_bus",
    "sem_20_arrayed_adapter_cross_node",
    "sem_23_nested_probe_contract_bus",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "expected_actual_delta_attribution_v0_35_35"


def _hypothesis_deltas(row: dict[str, Any]) -> list[int]:
    deltas: list[int] = []
    for step in row.get("steps", []):
        if not isinstance(step, dict):
            continue
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict) or call.get("name") != "record_repair_hypothesis":
                continue
            arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            try:
                deltas.append(int(arguments.get("expected_equation_delta")))
            except (TypeError, ValueError):
                continue
    return deltas


def _candidate_rows(run_dirs: list[Path], target_case_ids: list[str]) -> list[dict[str, Any]]:
    wanted = set(target_case_ids)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for run_dir in run_dirs:
        for row in load_jsonl(run_dir / "results.jsonl"):
            case_id = str(row.get("case_id") or "")
            if case_id in wanted and case_id not in seen:
                rows.append(row)
                seen.add(case_id)
    return rows


def build_expected_actual_delta_attribution(
    *,
    run_dirs: list[Path] | None = None,
    target_case_ids: list[str] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    ids = target_case_ids or DEFAULT_TARGET_CASE_IDS
    rows = _candidate_rows(dirs, ids)
    cases: list[dict[str, Any]] = []
    for row in rows:
        case = _case_summary(row)
        expected = _hypothesis_deltas(row)
        actual = case["post_consistency_candidate_zero_flow_counts"]
        cases.append(
            {
                "case_id": case["case_id"],
                "final_verdict": case["final_verdict"],
                "expected_equation_deltas": expected,
                "actual_zero_flow_equation_counts": actual,
                "expected_actual_mismatch": bool(expected and actual and expected[-1] != actual[-1]),
                "portfolio_expected_equation_deltas": case["portfolio_expected_equation_deltas"],
                "success_evidence_steps": case["success_evidence_steps"],
            }
        )
    mismatch_count = sum(1 for case in cases if case["expected_actual_mismatch"])
    if not rows:
        decision = "expected_actual_delta_attribution_incomplete"
    elif mismatch_count:
        decision = "llm_expected_delta_often_does_not_match_written_candidate"
    else:
        decision = "expected_actual_delta_matches_written_candidates"
    summary = {
        "version": "v0.35.35",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "expected_actual_delta_attribution",
        "case_count": len(cases),
        "mismatch_count": mismatch_count,
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
