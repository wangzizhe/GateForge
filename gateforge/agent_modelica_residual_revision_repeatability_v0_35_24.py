from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl
from .agent_modelica_residual_obedience_attribution_v0_35_22 import _case_row
from .agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "connector_flow_residual_revision_live_v0_35_23_sem22",
    REPO_ROOT / "artifacts" / "connector_flow_residual_revision_repeat_v0_35_24_sem22_run_02",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "residual_revision_repeatability_v0_35_24"


def _run_row(run_dir: Path, target_case_id: str) -> dict[str, Any] | None:
    rows = [row for row in load_jsonl(run_dir / "results.jsonl") if row.get("case_id") == target_case_id]
    if not rows:
        return None
    case = _case_row(rows[0])
    return {
        "run_id": run_dir.name,
        "pass_count": 1 if case["final_verdict"] == "PASS" else 0,
        "case": case,
    }


def build_residual_revision_repeatability(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
    target_case_id: str = TARGET_CASE_ID,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    runs: list[dict[str, Any]] = []
    missing_runs: list[str] = []
    for run_dir in dirs:
        row = _run_row(run_dir, target_case_id)
        if row is None:
            missing_runs.append(run_dir.name)
        else:
            runs.append(row)
    pass_counts = [run["pass_count"] for run in runs]
    violation_counts = [
        int(run["case"]["post_consistency_over_residual_candidate_count"])
        for run in runs
    ]
    if missing_runs:
        decision = "residual_revision_repeatability_incomplete"
    elif sum(pass_counts) == len(runs):
        decision = "residual_revision_stable_gain"
    elif sum(pass_counts) > 0:
        decision = "residual_revision_positive_but_unstable"
    else:
        decision = "residual_revision_not_repeatable"
    summary = {
        "version": "v0.35.24",
        "status": "PASS" if runs and not missing_runs else "REVIEW",
        "analysis_scope": "residual_revision_repeatability",
        "target_case_id": target_case_id,
        "run_count": len(runs),
        "missing_runs": missing_runs,
        "pass_counts": pass_counts,
        "post_consistency_violation_counts": violation_counts,
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
