from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_modelica_candidate_discovery_attribution_v0_30_5 import (
    REPO_ROOT,
    build_candidate_discovery_attribution,
    write_outputs,
)
from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "structure_coverage_probe_v0_31_2" / "run_02"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "structure_coverage_probe_v0_31_2" / "summary"


def _coverage_call_count(row: dict[str, Any]) -> int:
    return sum(
        1
        for step in row.get("steps", [])
        for call in step.get("tool_calls", [])
        if isinstance(call, dict) and call.get("name") == "structure_coverage_diagnostic"
    )


def build_structure_coverage_probe_summary(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_candidate_discovery_attribution(run_dirs={"run_02": run_dir}, out_dir=out_dir)
    rows = load_jsonl(run_dir / "results.jsonl")
    coverage_call_count = sum(_coverage_call_count(row) for row in rows)
    summary["version"] = "v0.31.2"
    summary["analysis_scope"] = "structure_coverage_probe"
    summary["coverage_call_count"] = coverage_call_count
    if coverage_call_count == 0:
        decision = "structure_coverage_not_invoked"
    elif summary["pass_count"] == 0:
        decision = "structure_coverage_invoked_without_discovery_gain"
    else:
        decision = "structure_coverage_positive_signal"
    summary["decision"] = decision
    write_outputs(out_dir=out_dir, summary=summary)
    return summary
