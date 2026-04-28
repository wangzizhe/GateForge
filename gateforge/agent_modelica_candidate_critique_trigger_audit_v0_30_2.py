from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_candidate_critique_summary_v0_30_0 import _critique_tool_count
from .agent_modelica_submit_discipline_summary_v0_29_23 import _row_summary, _rows

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = {
    "v0.30.0": REPO_ROOT / "artifacts" / "candidate_critique_probe_v0_30_0" / "run_01",
    "v0.30.1": REPO_ROOT / "artifacts" / "candidate_critique_salience_v0_30_1" / "run_01",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_critique_trigger_audit_v0_30_2"


def _tool_names_after_step(row: dict[str, Any], first_step: int | None) -> list[str]:
    if first_step is None:
        return []
    names: list[str] = []
    for step in row.get("steps", []):
        step_id = step.get("step")
        if not isinstance(step_id, int) or step_id <= first_step:
            continue
        for call in step.get("tool_calls", []):
            if isinstance(call, dict) and call.get("name"):
                names.append(str(call["name"]))
    return names


def _audit_row(*, version: str, case_id: str, row: dict[str, Any]) -> dict[str, Any]:
    summary = _row_summary(row)
    critique_count = _critique_tool_count(row)
    trigger_opportunity = (
        bool(summary["successful_candidate_observed"])
        and not bool(summary["submitted"])
        and critique_count == 0
    )
    return {
        "version": version,
        "case_id": case_id,
        "verdict": summary["verdict"],
        "submitted": summary["submitted"],
        "successful_candidate_observed": summary["successful_candidate_observed"],
        "first_successful_tool_step": summary["first_successful_tool_step"],
        "missed_successful_candidate": summary["missed_successful_candidate"],
        "critique_tool_count": critique_count,
        "trigger_opportunity": trigger_opportunity,
        "post_success_tool_names": _tool_names_after_step(row, summary["first_successful_tool_step"]),
        "token_used": summary["token_used"],
        "unique_candidate_count": summary["unique_candidate_count"],
    }


def build_candidate_critique_trigger_audit(
    *,
    run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    active_run_dirs = run_dirs or DEFAULT_RUN_DIRS
    rows: list[dict[str, Any]] = []
    for version, run_dir in active_run_dirs.items():
        for case_id, row in sorted(_rows(run_dir).items()):
            rows.append(_audit_row(version=version, case_id=case_id, row=row))

    trigger_opportunities = [row for row in rows if row["trigger_opportunity"]]
    critique_invocations = sum(int(row["critique_tool_count"]) for row in rows)
    missed_success_count = sum(1 for row in rows if row["missed_successful_candidate"])
    if trigger_opportunities:
        decision = "transparent_checkpoint_needed"
    elif critique_invocations:
        decision = "candidate_critique_trigger_sufficient"
    else:
        decision = "no_trigger_evidence"

    summary = {
        "version": "v0.30.2",
        "status": "PASS" if rows else "REVIEW",
        "analysis_scope": "candidate_critique_trigger_audit",
        "run_count": len(active_run_dirs),
        "row_count": len(rows),
        "missed_success_count": missed_success_count,
        "critique_invocation_count": critique_invocations,
        "trigger_opportunity_count": len(trigger_opportunities),
        "trigger_opportunities": trigger_opportunities,
        "rows": rows,
        "decision": decision,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
