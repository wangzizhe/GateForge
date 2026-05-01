from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_connector_flow_family_live_attribution_v0_35_1 import _classify_run
from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_RUN_DIRS = {
    "base": REPO_ROOT / "artifacts" / "connector_flow_family_base_live_v0_35_3",
    "connector_flow_semantics": REPO_ROOT / "artifacts" / "connector_flow_family_live_v0_35_1",
    "connector_flow_submit_checkpoint": REPO_ROOT / "artifacts" / "connector_flow_family_checkpoint_live_v0_35_2",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_family_profile_comparison_v0_35_3"


def _profile_summary(profile: str, run_dir: Path) -> dict[str, Any]:
    rows = load_jsonl(run_dir / "results.jsonl")
    cases = [_classify_run(row) for row in rows]
    class_counts: dict[str, int] = {}
    for case in cases:
        outcome_class = str(case["outcome_class"])
        class_counts[outcome_class] = class_counts.get(outcome_class, 0) + 1
    return {
        "profile": profile,
        "run_id": run_dir.name,
        "case_count": len(cases),
        "pass_count": sum(1 for case in cases if case["final_verdict"] == "PASS"),
        "submitted_count": sum(1 for case in cases if case["submitted"]),
        "success_candidate_seen_count": sum(1 for case in cases if case["success_evidence_steps"]),
        "diagnostic_invoked_count": sum(1 for case in cases if case["diagnostic_call_count"] > 0),
        "submit_call_count": sum(int(case["submit_call_count"]) for case in cases),
        "outcome_class_counts": dict(sorted(class_counts.items())),
        "cases": cases,
    }


def build_connector_flow_family_profile_comparison(
    *,
    profile_run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    run_dirs = profile_run_dirs or DEFAULT_PROFILE_RUN_DIRS
    profiles = [_profile_summary(profile, run_dir) for profile, run_dir in sorted(run_dirs.items())]
    missing_profiles = [profile["profile"] for profile in profiles if profile["case_count"] == 0]
    best_pass_count = max((int(profile["pass_count"]) for profile in profiles), default=0)
    best_success_candidate_seen = max(
        (int(profile["success_candidate_seen_count"]) for profile in profiles),
        default=0,
    )
    if missing_profiles:
        decision = "connector_flow_profile_comparison_incomplete"
    elif best_pass_count:
        decision = "connector_flow_profile_has_live_passes"
    elif best_success_candidate_seen:
        decision = "connector_flow_profiles_expose_delivery_gap_without_pass_gain"
    else:
        decision = "connector_flow_profiles_expose_candidate_discovery_gap"
    summary = {
        "version": "v0.35.3",
        "status": "PASS" if profiles and not missing_profiles else "REVIEW",
        "analysis_scope": "connector_flow_family_profile_comparison",
        "profile_count": len(profiles),
        "missing_profiles": missing_profiles,
        "best_pass_count": best_pass_count,
        "best_success_candidate_seen_count": best_success_candidate_seen,
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
