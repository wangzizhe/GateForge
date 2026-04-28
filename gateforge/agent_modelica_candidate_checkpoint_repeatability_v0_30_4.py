from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_candidate_checkpoint_summary_v0_30_3 import _checkpoint_count, _checkpoint_guard_count
from .agent_modelica_candidate_critique_summary_v0_30_0 import _critique_tool_count
from .agent_modelica_submit_discipline_summary_v0_29_23 import _row_summary, _rows

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = {
    "run_01": REPO_ROOT / "artifacts" / "candidate_checkpoint_probe_v0_30_3" / "run_01",
    "run_02": REPO_ROOT / "artifacts" / "candidate_checkpoint_repeatability_v0_30_4" / "run_02",
    "run_03": REPO_ROOT / "artifacts" / "candidate_checkpoint_repeatability_v0_30_4" / "run_03",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_checkpoint_repeatability_v0_30_4" / "summary"


def build_candidate_checkpoint_repeatability_summary(
    *,
    run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    active_run_dirs = run_dirs or DEFAULT_RUN_DIRS
    rows_by_run = {run_id: _rows(run_dir) for run_id, run_dir in active_run_dirs.items()}
    case_ids = sorted({case_id for rows in rows_by_run.values() for case_id in rows})
    runs: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []

    for run_id, rows in sorted(rows_by_run.items()):
        pass_count = sum(1 for row in rows.values() if row.get("final_verdict") == "PASS")
        checkpoint_count = sum(_checkpoint_count(row) for row in rows.values())
        guard_count = sum(_checkpoint_guard_count(row) for row in rows.values())
        missed_count = sum(1 for row in rows.values() if _row_summary(row)["missed_successful_candidate"])
        runs.append(
            {
                "run_id": run_id,
                "case_count": len(rows),
                "pass_count": pass_count,
                "missed_success_count": missed_count,
                "checkpoint_count": checkpoint_count,
                "checkpoint_guard_count": guard_count,
                "critique_tool_count": sum(_critique_tool_count(row) for row in rows.values()),
            }
        )

    for case_id in case_ids:
        verdicts: dict[str, str] = {}
        submitted: dict[str, bool] = {}
        checkpoint_counts: dict[str, int] = {}
        guard_counts: dict[str, int] = {}
        missed_counts: dict[str, bool] = {}
        for run_id, rows in sorted(rows_by_run.items()):
            row = rows.get(case_id, {})
            summary = _row_summary(row)
            verdicts[run_id] = summary["verdict"]
            submitted[run_id] = bool(summary["submitted"])
            checkpoint_counts[run_id] = _checkpoint_count(row)
            guard_counts[run_id] = _checkpoint_guard_count(row)
            missed_counts[run_id] = bool(summary["missed_successful_candidate"])
        pass_count = sum(1 for verdict in verdicts.values() if verdict == "PASS")
        case_rows.append(
            {
                "case_id": case_id,
                "pass_count": pass_count,
                "run_count": len(verdicts),
                "stable_pass": pass_count == len(verdicts),
                "stable_fail": pass_count == 0,
                "mixed": 0 < pass_count < len(verdicts),
                "verdicts": verdicts,
                "submitted": submitted,
                "checkpoint_counts": checkpoint_counts,
                "checkpoint_guard_counts": guard_counts,
                "missed_success": missed_counts,
            }
        )

    run_pass_counts = [int(run["pass_count"]) for run in runs]
    stable_pass_cases = sum(1 for row in case_rows if row["stable_pass"])
    mixed_cases = sum(1 for row in case_rows if row["mixed"])
    if not runs:
        decision = "checkpoint_repeatability_needs_runs"
    elif min(run_pass_counts) >= 3 and mixed_cases == 0:
        decision = "checkpoint_repeatability_stable_positive"
    elif max(run_pass_counts) > min(run_pass_counts):
        decision = "checkpoint_positive_but_unstable"
    else:
        decision = "checkpoint_no_repeatable_gain"

    summary = {
        "version": "v0.30.4",
        "status": "PASS" if runs else "REVIEW",
        "analysis_scope": "candidate_checkpoint_repeatability",
        "run_count": len(runs),
        "case_count": len(case_rows),
        "run_pass_counts": run_pass_counts,
        "min_pass_count": min(run_pass_counts) if run_pass_counts else 0,
        "max_pass_count": max(run_pass_counts) if run_pass_counts else 0,
        "stable_pass_case_count": stable_pass_cases,
        "mixed_case_count": mixed_cases,
        "runs": runs,
        "cases": case_rows,
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
