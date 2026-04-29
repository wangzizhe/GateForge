from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_connector_flow_semantics_attribution_v0_34_15 import (
    _balanced_without_success,
    _has_success,
    _tool_names,
)
from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "connector_flow_submit_checkpoint_live_probe_v0_34_16_sem19_run_01",
    REPO_ROOT / "artifacts" / "connector_flow_submit_checkpoint_repeat_v0_34_18_sem19_run_02",
    REPO_ROOT / "artifacts" / "connector_flow_submit_checkpoint_repeat_v0_34_18_sem19_run_03",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "connector_flow_checkpoint_repeatability_v0_34_18"


def _run_row(run_dir: Path) -> dict[str, Any] | None:
    rows = load_jsonl(run_dir / "results.jsonl")
    if not rows:
        return None
    row = rows[0]
    steps = [step for step in row.get("steps", []) if isinstance(step, dict)]
    tool_sequence = [name for step in steps for name in _tool_names(step)]
    success_steps = [int(step.get("step") or 0) for step in steps if _has_success(step)]
    balanced_steps = [int(step.get("step") or 0) for step in steps if _balanced_without_success(step)]
    checkpoint_message_count = sum(len(step.get("checkpoint_messages", [])) for step in steps)
    checkpoint_guard_count = sum(len(step.get("checkpoint_guard_violations", [])) for step in steps)
    if bool(row.get("submitted")):
        failure_class = "submitted_success"
    elif success_steps:
        failure_class = "success_candidate_seen_without_submit"
    elif balanced_steps:
        failure_class = "balanced_without_simulation_success"
    else:
        failure_class = "candidate_discovery_failure"
    return {
        "run_id": run_dir.name,
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "provider_error": str(row.get("provider_error") or ""),
        "step_count": int(row.get("step_count") or 0),
        "token_used": int(row.get("token_used") or 0),
        "diagnostic_call_count": tool_sequence.count("connector_flow_semantics_diagnostic"),
        "success_evidence_steps": success_steps,
        "balanced_without_success_steps": balanced_steps,
        "checkpoint_message_count": checkpoint_message_count,
        "checkpoint_guard_count": checkpoint_guard_count,
        "submit_call_count": tool_sequence.count("submit_final"),
        "tool_sequence": tool_sequence,
        "failure_class": failure_class,
    }


def build_connector_flow_checkpoint_repeatability(
    *,
    run_dirs: list[Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    dirs = run_dirs or DEFAULT_RUN_DIRS
    rows: list[dict[str, Any]] = []
    missing_runs: list[str] = []
    for run_dir in dirs:
        row = _run_row(run_dir)
        if row is None:
            missing_runs.append(run_dir.name)
            continue
        rows.append(row)
    class_counts: dict[str, int] = {}
    for row in rows:
        failure_class = str(row["failure_class"])
        class_counts[failure_class] = class_counts.get(failure_class, 0) + 1
    success_count = sum(1 for row in rows if row["success_evidence_steps"])
    checkpoint_message_count = sum(int(row["checkpoint_message_count"]) for row in rows)
    pass_count = sum(1 for row in rows if row["final_verdict"] == "PASS")
    if pass_count:
        decision = "connector_flow_checkpoint_has_positive_signal"
    elif checkpoint_message_count:
        decision = "connector_flow_checkpoint_triggered_without_pass"
    elif success_count:
        decision = "connector_flow_checkpoint_not_triggered_despite_success"
    else:
        decision = "connector_flow_checkpoint_not_reached_candidate_discovery_unstable"
    summary = {
        "version": "v0.34.18",
        "status": "PASS" if rows and not missing_runs else "REVIEW",
        "analysis_scope": "connector_flow_submit_checkpoint_repeatability",
        "run_count": len(rows),
        "missing_runs": missing_runs,
        "pass_count": pass_count,
        "submitted_count": sum(1 for row in rows if row["submitted"]),
        "diagnostic_invoked_count": sum(1 for row in rows if row["diagnostic_call_count"] > 0),
        "success_candidate_seen_count": success_count,
        "checkpoint_message_count": checkpoint_message_count,
        "checkpoint_guard_count": sum(int(row["checkpoint_guard_count"]) for row in rows),
        "failure_class_counts": class_counts,
        "runs": rows,
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
