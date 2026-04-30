from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_connector_flow_family_live_attribution_v0_35_1 import _classify_run
from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "connector_flow_family_checkpoint_live_v0_35_2"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_checkpoint_family_attribution_v0_35_2"


def build_connector_flow_checkpoint_family_attribution(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases = [_classify_run(row) for row in rows]
    class_counts: dict[str, int] = {}
    for case in cases:
        outcome_class = str(case["outcome_class"])
        class_counts[outcome_class] = class_counts.get(outcome_class, 0) + 1
    pass_count = sum(1 for case in cases if case["final_verdict"] == "PASS")
    success_candidate_seen_count = sum(1 for case in cases if case["success_evidence_steps"])
    submit_call_count = sum(int(case["submit_call_count"]) for case in cases)
    diagnostic_invoked_count = sum(1 for case in cases if case["diagnostic_call_count"] > 0)
    if not rows:
        decision = "missing_connector_flow_checkpoint_family_live_run"
    elif pass_count:
        decision = "connector_flow_checkpoint_family_has_live_successes"
    elif success_candidate_seen_count and submit_call_count == 0:
        decision = "connector_flow_checkpoint_family_did_not_trigger_after_success_candidate"
    elif diagnostic_invoked_count:
        decision = "connector_flow_checkpoint_family_exposes_candidate_discovery_gap"
    else:
        decision = "connector_flow_checkpoint_family_not_engaged"
    summary = {
        "version": "v0.35.2",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "connector_flow_checkpoint_family_attribution",
        "run_id": run_dir.name,
        "case_count": len(cases),
        "pass_count": pass_count,
        "submitted_count": sum(1 for case in cases if case["submitted"]),
        "submit_call_count": submit_call_count,
        "diagnostic_invoked_count": diagnostic_invoked_count,
        "success_candidate_seen_count": success_candidate_seen_count,
        "outcome_class_counts": dict(sorted(class_counts.items())),
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
