from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_modelica_candidate_discovery_attribution_v0_30_5 import (
    REPO_ROOT,
    build_candidate_discovery_attribution,
)

DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "multicandidate_checkpoint_probe_v0_30_6" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "multicandidate_checkpoint_probe_v0_30_6" / "summary"


def build_multicandidate_checkpoint_summary(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_candidate_discovery_attribution(run_dirs={"run_01": run_dir}, out_dir=out_dir)
    summary["version"] = "v0.30.6"
    summary["analysis_scope"] = "multicandidate_checkpoint_probe"
    summary["decision"] = (
        "multicandidate_checkpoint_no_discovery_gain"
        if summary["pass_count"] <= 1
        else "multicandidate_checkpoint_positive_signal"
    )
    from .agent_modelica_candidate_discovery_attribution_v0_30_5 import write_outputs

    write_outputs(out_dir=out_dir, summary=summary)
    return summary
