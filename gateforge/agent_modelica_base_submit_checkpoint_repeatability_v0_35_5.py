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
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "connector_flow_family_base_checkpoint_live_v0_35_4",
    REPO_ROOT / "artifacts" / "base_submit_checkpoint_repeat_v0_35_5_run_02",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "base_submit_checkpoint_repeatability_v0_35_5"


def _run_summary(run_dir: Path) -> dict[str, Any] | None:
    rows = load_jsonl(run_dir / "results.jsonl")
    if not rows:
        return None
    cases: list[dict[str, Any]] = []
    for row in rows:
        case = _classify_run(row)
        case["checkpoint_message_count"] = _checkpoint_message_count(row)
        case["checkpoint_guard_violations"] = _checkpoint_guard_violations(row)
        cases.append(case)
    return {
        "run_id": run_dir.name,
        "case_count": len(cases),
        "pass_count": sum(1 for case in cases if case["final_verdict"] == "PASS"),
        "submitted_count": sum(1 for case in cases if case["submitted"]),
        "success_candidate_seen_count": sum(1 for case in cases if case["success_evidence_steps"]),
        "checkpoint_message_count": sum(int(case["checkpoint_message_count"]) for case in cases),
        "checkpoint_guard_violation_count": sum(len(case["checkpoint_guard_violations"]) for case in cases),
        "passed_case_ids": [case["case_id"] for case in cases if case["final_verdict"] == "PASS"],
        "cases": cases,
    }


def build_base_submit_checkpoint_repeatability(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    runs: list[dict[str, Any]] = []
    missing_runs: list[str] = []
    for run_dir in dirs:
        run = _run_summary(run_dir)
        if run is None:
            missing_runs.append(run_dir.name)
        else:
            runs.append(run)
    pass_counts = [int(run["pass_count"]) for run in runs]
    passed_case_sets = [set(str(case_id) for case_id in run["passed_case_ids"]) for run in runs]
    stable_pass_case_ids = sorted(set.intersection(*passed_case_sets)) if passed_case_sets else []
    if missing_runs:
        decision = "base_submit_checkpoint_repeatability_incomplete"
    elif stable_pass_case_ids:
        decision = "base_submit_checkpoint_has_stable_passes"
    elif any(pass_counts):
        decision = "base_submit_checkpoint_improves_delivery_but_candidate_discovery_varies"
    else:
        decision = "base_submit_checkpoint_no_repeatable_gain"
    summary = {
        "version": "v0.35.5",
        "status": "PASS" if runs and not missing_runs else "REVIEW",
        "analysis_scope": "base_submit_checkpoint_repeatability",
        "run_count": len(runs),
        "missing_runs": missing_runs,
        "total_case_attempts": sum(int(run["case_count"]) for run in runs),
        "total_pass_count": sum(pass_counts),
        "pass_counts": pass_counts,
        "stable_pass_case_ids": stable_pass_case_ids,
        "runs": runs,
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
