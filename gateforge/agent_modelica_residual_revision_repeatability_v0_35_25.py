from __future__ import annotations

from pathlib import Path

from .agent_modelica_residual_revision_repeatability_v0_35_24 import (
    REPO_ROOT,
    build_residual_revision_repeatability,
)

DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "connector_flow_residual_revision_live_v0_35_23_sem22",
    REPO_ROOT / "artifacts" / "connector_flow_residual_revision_repeat_v0_35_24_sem22_run_02",
    REPO_ROOT / "artifacts" / "connector_flow_residual_revision_repeat_v0_35_25_sem22_run_03",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "residual_revision_repeatability_v0_35_25"


def build_residual_revision_repeatability_v0_35_25(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict:
    summary = build_residual_revision_repeatability(run_dirs=run_dirs or DEFAULT_RUN_DIRS, out_dir=out_dir)
    summary["version"] = "v0.35.25"
    pass_counts = list(summary.get("pass_counts") or [])
    if summary.get("status") != "PASS":
        summary["decision"] = "residual_revision_repeatability_incomplete"
    elif sum(pass_counts) == 0:
        summary["decision"] = "residual_revision_not_repeatable"
    elif sum(pass_counts) < len(pass_counts):
        summary["decision"] = "residual_revision_positive_but_unstable_not_defaultable"
    else:
        summary["decision"] = "residual_revision_stable_gain"
    return summary
