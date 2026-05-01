from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_modelica_candidate_discovery_attribution_v0_30_5 import (
    REPO_ROOT,
    build_candidate_discovery_attribution,
    write_outputs,
)

DEFAULT_RUN_DIR = REPO_ROOT / "artifacts" / "structure_plan_checkpoint_probe_v0_30_10" / "run_01"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "structure_plan_checkpoint_probe_v0_30_10" / "summary"


def _strategy_call_count(row: dict[str, Any]) -> int:
    return sum(
        1
        for step in row.get("steps", [])
        for call in step.get("tool_calls", [])
        if isinstance(call, dict) and call.get("name") == "record_structure_strategies"
    )


def build_structure_plan_checkpoint_summary(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_candidate_discovery_attribution(run_dirs={"run_01": run_dir}, out_dir=out_dir)
    from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

    rows = load_jsonl(run_dir / "results.jsonl")
    strategy_call_count = sum(_strategy_call_count(row) for row in rows)
    summary["version"] = "v0.30.10"
    summary["analysis_scope"] = "structure_plan_checkpoint_probe"
    summary["strategy_call_count"] = strategy_call_count
    if strategy_call_count == 0:
        decision = "structure_plan_not_invoked"
    elif summary["pass_count"] <= 1:
        decision = "structure_plan_invoked_without_discovery_gain"
    else:
        decision = "structure_plan_positive_signal"
    summary["decision"] = decision
    write_outputs(out_dir=out_dir, summary=summary)
    return summary
