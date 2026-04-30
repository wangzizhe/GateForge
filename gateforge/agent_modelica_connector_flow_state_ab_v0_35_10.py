from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_base_submit_checkpoint_attribution_v0_35_4 import (
    _checkpoint_guard_violations,
    _checkpoint_message_count,
)
from .agent_modelica_connector_flow_family_live_attribution_v0_35_1 import _classify_run
from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = {
    "base_submit_checkpoint_run_01": REPO_ROOT / "artifacts" / "connector_flow_family_base_checkpoint_live_v0_35_4",
    "base_submit_checkpoint_run_02": REPO_ROOT / "artifacts" / "base_submit_checkpoint_repeat_v0_35_5_run_02",
    "connector_flow_state_checkpoint": REPO_ROOT / "artifacts" / "connector_flow_state_checkpoint_live_v0_35_10",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_state_ab_v0_35_10"


def _profile_rows(profile: str, run_dir: Path) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases: list[dict[str, Any]] = []
    for row in rows:
        case = _classify_run(row)
        tool_names = [
            str(call.get("name") or "")
            for step in row.get("steps", [])
            if isinstance(step, dict)
            for call in step.get("tool_calls", [])
            if isinstance(call, dict)
        ]
        case["state_diagnostic_call_count"] = tool_names.count("connector_flow_state_diagnostic")
        case["checkpoint_message_count"] = _checkpoint_message_count(row)
        case["checkpoint_guard_violations"] = _checkpoint_guard_violations(row)
        cases.append(case)
    return {
        "profile": profile,
        "run_id": run_dir.name,
        "case_count": len(cases),
        "pass_count": sum(1 for case in cases if case["final_verdict"] == "PASS"),
        "submitted_count": sum(1 for case in cases if case["submitted"]),
        "success_candidate_seen_count": sum(1 for case in cases if case["success_evidence_steps"]),
        "diagnostic_invoked_count": sum(
            1
            for case in cases
            if case["diagnostic_call_count"] > 0 or case["state_diagnostic_call_count"] > 0
        ),
        "state_diagnostic_invoked_count": sum(1 for case in cases if case["state_diagnostic_call_count"] > 0),
        "checkpoint_message_count": sum(int(case["checkpoint_message_count"]) for case in cases),
        "passed_case_ids": [case["case_id"] for case in cases if case["final_verdict"] == "PASS"],
        "cases": cases,
    }


def build_connector_flow_state_ab(
    *,
    run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    profiles = [_profile_rows(profile, run_dir) for profile, run_dir in sorted(dirs.items())]
    missing_profiles = [profile["profile"] for profile in profiles if profile["case_count"] == 0]
    state_profiles = [profile for profile in profiles if profile["profile"] == "connector_flow_state_checkpoint"]
    state_pass_count = int(state_profiles[0]["pass_count"]) if state_profiles else 0
    baseline_best_pass_count = max(
        (int(profile["pass_count"]) for profile in profiles if profile["profile"] != "connector_flow_state_checkpoint"),
        default=0,
    )
    if missing_profiles:
        decision = "connector_flow_state_ab_incomplete"
    elif state_pass_count > baseline_best_pass_count:
        decision = "connector_flow_state_improves_pass_count"
    elif state_pass_count == baseline_best_pass_count and state_pass_count > 0:
        decision = "connector_flow_state_matches_checkpoint_baseline"
    else:
        decision = "connector_flow_state_no_live_gain"
    summary = {
        "version": "v0.35.10",
        "status": "PASS" if profiles and not missing_profiles else "REVIEW",
        "analysis_scope": "connector_flow_state_ab",
        "profile_count": len(profiles),
        "missing_profiles": missing_profiles,
        "state_pass_count": state_pass_count,
        "baseline_best_pass_count": baseline_best_pass_count,
        "profiles": profiles,
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
