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
    "base": REPO_ROOT / "artifacts" / "connector_flow_family_base_live_v0_35_3",
    "connector_flow_semantics": REPO_ROOT / "artifacts" / "connector_flow_family_live_v0_35_1",
    "connector_flow_submit_checkpoint": REPO_ROOT / "artifacts" / "connector_flow_family_checkpoint_live_v0_35_2",
    "base_submit_checkpoint_run_01": REPO_ROOT / "artifacts" / "connector_flow_family_base_checkpoint_live_v0_35_4",
    "base_submit_checkpoint_run_02": REPO_ROOT / "artifacts" / "base_submit_checkpoint_repeat_v0_35_5_run_02",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_discovery_delivery_decomposition_v0_35_6"


def _attempts_for_profile(profile: str, run_dir: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(run_dir / "results.jsonl")
    attempts: list[dict[str, Any]] = []
    for row in rows:
        attempt = _classify_run(row)
        attempt["profile"] = profile
        attempt["run_id"] = run_dir.name
        attempt["checkpoint_message_count"] = _checkpoint_message_count(row)
        attempt["checkpoint_guard_violations"] = _checkpoint_guard_violations(row)
        attempts.append(attempt)
    return attempts


def build_candidate_discovery_delivery_decomposition(
    *,
    run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    attempts: list[dict[str, Any]] = []
    missing_profiles: list[str] = []
    for profile, run_dir in sorted(dirs.items()):
        profile_attempts = _attempts_for_profile(profile, run_dir)
        if not profile_attempts:
            missing_profiles.append(profile)
        attempts.extend(profile_attempts)

    outcome_counts: dict[str, int] = {}
    case_counts: dict[str, dict[str, int]] = {}
    profile_counts: dict[str, dict[str, int]] = {}
    for attempt in attempts:
        outcome = str(attempt["outcome_class"])
        case_id = str(attempt["case_id"])
        profile = str(attempt["profile"])
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        case_counts.setdefault(case_id, {})
        case_counts[case_id][outcome] = case_counts[case_id].get(outcome, 0) + 1
        profile_counts.setdefault(profile, {})
        profile_counts[profile][outcome] = profile_counts[profile].get(outcome, 0) + 1

    candidate_success_attempts = [
        attempt for attempt in attempts if attempt["outcome_class"] in {"submitted_success", "success_candidate_seen_without_submit"}
    ]
    submitted_success_count = outcome_counts.get("submitted_success", 0)
    missed_success_count = outcome_counts.get("success_candidate_seen_without_submit", 0)
    discovery_failure_count = outcome_counts.get("candidate_discovery_failure", 0)
    if missing_profiles:
        decision = "candidate_discovery_delivery_decomposition_incomplete"
    elif discovery_failure_count > submitted_success_count + missed_success_count:
        decision = "candidate_discovery_is_primary_bottleneck"
    elif missed_success_count:
        decision = "delivery_discipline_is_primary_bottleneck"
    else:
        decision = "no_clear_candidate_delivery_bottleneck"

    summary = {
        "version": "v0.35.6",
        "status": "PASS" if attempts and not missing_profiles else "REVIEW",
        "analysis_scope": "candidate_discovery_delivery_decomposition",
        "profile_count": len(dirs),
        "missing_profiles": missing_profiles,
        "attempt_count": len(attempts),
        "case_count": len(case_counts),
        "candidate_success_attempt_count": len(candidate_success_attempts),
        "submitted_success_count": submitted_success_count,
        "missed_success_count": missed_success_count,
        "discovery_failure_count": discovery_failure_count,
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "case_outcome_counts": {case_id: dict(sorted(counts.items())) for case_id, counts in sorted(case_counts.items())},
        "profile_outcome_counts": {
            profile: dict(sorted(counts.items()))
            for profile, counts in sorted(profile_counts.items())
        },
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
