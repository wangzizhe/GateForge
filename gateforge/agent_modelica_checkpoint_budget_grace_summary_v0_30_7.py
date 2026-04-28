from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_modelica_candidate_discovery_attribution_v0_30_5 import (
    REPO_ROOT,
    build_candidate_discovery_attribution,
    write_outputs,
)

DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "checkpoint_budget_grace_probe_v0_30_7" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "checkpoint_budget_grace_probe_v0_30_7" / "summary"


def build_checkpoint_budget_grace_summary(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_candidate_discovery_attribution(run_dirs={"run_01": run_dir}, out_dir=out_dir)
    summary["version"] = "v0.30.7"
    summary["analysis_scope"] = "checkpoint_budget_grace_probe"
    summary["decision"] = (
        "checkpoint_budget_grace_positive_signal"
        if summary["pass_count"] >= 3 and summary["discovery_failure_count"] == 0
        else "checkpoint_budget_grace_no_clear_gain"
    )
    write_outputs(out_dir=out_dir, summary=summary)
    return summary
