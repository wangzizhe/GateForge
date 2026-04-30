from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_connector_flow_state_ab_v0_35_10 import _profile_rows

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "connector_flow_state_checkpoint_live_v0_35_10",
    REPO_ROOT / "artifacts" / "connector_flow_state_checkpoint_repeat_v0_35_11_run_02",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_state_repeatability_v0_35_11"


def build_connector_flow_state_repeatability(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    runs: list[dict[str, Any]] = []
    missing_runs: list[str] = []
    for idx, run_dir in enumerate(dirs, start=1):
        run = _profile_rows(f"connector_flow_state_checkpoint_run_{idx:02d}", run_dir)
        if run["case_count"] == 0:
            missing_runs.append(run_dir.name)
        else:
            runs.append(run)
    pass_counts = [int(run["pass_count"]) for run in runs]
    diagnostic_counts = [int(run["state_diagnostic_invoked_count"]) for run in runs]
    passed_case_sets = [set(str(case_id) for case_id in run["passed_case_ids"]) for run in runs]
    stable_pass_case_ids = sorted(set.intersection(*passed_case_sets)) if passed_case_sets else []
    if missing_runs:
        decision = "connector_flow_state_repeatability_incomplete"
    elif stable_pass_case_ids:
        decision = "connector_flow_state_has_stable_passes"
    elif any(pass_counts):
        decision = "connector_flow_state_positive_but_unstable"
    else:
        decision = "connector_flow_state_no_repeatable_candidate_discovery_gain"
    summary = {
        "version": "v0.35.11",
        "status": "PASS" if runs and not missing_runs else "REVIEW",
        "analysis_scope": "connector_flow_state_repeatability",
        "run_count": len(runs),
        "missing_runs": missing_runs,
        "pass_counts": pass_counts,
        "state_diagnostic_invoked_counts": diagnostic_counts,
        "total_pass_count": sum(pass_counts),
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
