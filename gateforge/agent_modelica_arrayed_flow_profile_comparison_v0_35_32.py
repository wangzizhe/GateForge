from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_DIR = REPO_ROOT / "artifacts" / "arrayed_flow_base_checkpoint_live_v0_35_32"
DEFAULT_CANDIDATE_DIR = REPO_ROOT / "artifacts" / "arrayed_flow_candidate_preference_live_v0_35_31"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "arrayed_flow_profile_comparison_v0_35_32"


def _verdicts(run_dir: Path) -> dict[str, str]:
    return {
        str(row.get("case_id") or ""): str(row.get("final_verdict") or "")
        for row in load_jsonl(run_dir / "results.jsonl")
        if row.get("case_id")
    }


def build_arrayed_flow_profile_comparison(
    *,
    base_dir: Path = DEFAULT_BASE_DIR,
    candidate_dir: Path = DEFAULT_CANDIDATE_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    base = _verdicts(base_dir)
    candidate = _verdicts(candidate_dir)
    case_ids = sorted(set(base) | set(candidate))
    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        base_pass = base.get(case_id) == "PASS"
        candidate_pass = candidate.get(case_id) == "PASS"
        if candidate_pass and not base_pass:
            delta = "improved"
        elif base_pass and not candidate_pass:
            delta = "regressed"
        elif candidate_pass and base_pass:
            delta = "stable_pass"
        else:
            delta = "stable_fail"
        cases.append(
            {
                "case_id": case_id,
                "base_verdict": base.get(case_id, "MISSING"),
                "candidate_preference_verdict": candidate.get(case_id, "MISSING"),
                "delta": delta,
            }
        )
    improved = [case["case_id"] for case in cases if case["delta"] == "improved"]
    regressed = [case["case_id"] for case in cases if case["delta"] == "regressed"]
    base_pass_count = sum(1 for verdict in base.values() if verdict == "PASS")
    candidate_pass_count = sum(1 for verdict in candidate.values() if verdict == "PASS")
    if not base or not candidate:
        decision = "arrayed_flow_profile_comparison_incomplete"
    elif candidate_pass_count > base_pass_count:
        decision = "candidate_preference_family_positive"
    elif candidate_pass_count < base_pass_count:
        decision = "candidate_preference_family_regresses"
    else:
        decision = "candidate_preference_family_neutral"
    summary = {
        "version": "v0.35.32",
        "status": "PASS" if base and candidate else "REVIEW",
        "analysis_scope": "arrayed_flow_profile_comparison",
        "case_count": len(case_ids),
        "base_pass_count": base_pass_count,
        "candidate_preference_pass_count": candidate_pass_count,
        "improved_case_ids": improved,
        "regressed_case_ids": regressed,
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
