from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_modelica_candidate_discovery_attribution_v0_30_5 import (
    REPO_ROOT,
    build_candidate_discovery_attribution,
    write_outputs,
)

DEFAULT_RUN_DIRS = {
    "run_01": REPO_ROOT / "artifacts" / "checkpoint_budget_grace_probe_v0_30_7" / "run_01",
    "run_02": REPO_ROOT / "artifacts" / "checkpoint_budget_grace_repeatability_v0_30_8" / "run_02",
    "run_03": REPO_ROOT / "artifacts" / "checkpoint_budget_grace_repeatability_v0_30_8" / "run_03",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "checkpoint_budget_grace_repeatability_v0_30_8" / "summary"


def build_checkpoint_budget_grace_repeatability(
    *,
    run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    active_run_dirs = run_dirs or DEFAULT_RUN_DIRS
    summary = build_candidate_discovery_attribution(run_dirs=active_run_dirs, out_dir=out_dir)
    run_pass_counts: list[int] = []
    for run_id in sorted(active_run_dirs):
        run_pass_counts.append(
            sum(
                1
                for case in summary["cases"]
                for row in case["runs"]
                if row["run_id"] == run_id and row["status"] == "pass"
            )
        )
    summary["version"] = "v0.30.8"
    summary["analysis_scope"] = "checkpoint_budget_grace_repeatability"
    summary["run_pass_counts"] = run_pass_counts
    summary["min_pass_count"] = min(run_pass_counts) if run_pass_counts else 0
    summary["max_pass_count"] = max(run_pass_counts) if run_pass_counts else 0
    if not run_pass_counts:
        decision = "checkpoint_budget_grace_repeatability_needs_runs"
    elif min(run_pass_counts) >= 3:
        decision = "checkpoint_budget_grace_stable_positive"
    elif max(run_pass_counts) >= 3:
        decision = "checkpoint_budget_grace_positive_but_unstable"
    else:
        decision = "checkpoint_budget_grace_not_supported"
    summary["decision"] = decision
    write_outputs(out_dir=out_dir, summary=summary)
    return summary
