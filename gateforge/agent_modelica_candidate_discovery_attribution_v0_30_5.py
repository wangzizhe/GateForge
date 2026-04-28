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
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_discovery_attribution_v0_30_5"


def _tool_call_count(row: dict[str, Any], name: str) -> int:
    return sum(
        1
        for step in row.get("steps", [])
        for call in step.get("tool_calls", [])
        if isinstance(call, dict) and call.get("name") == name
    )


def _failed_check_excerpt(row: dict[str, Any]) -> str:
    for step in reversed(row.get("steps", [])):
        for result in step.get("tool_results", []):
            if not isinstance(result, dict):
                continue
            if result.get("name") not in {"check_model", "simulate_model"}:
                continue
            text = str(result.get("result") or "")
            if 'resultFile = "/workspace/' not in text:
                return text[:500]
    return ""


def _run_case_row(*, run_id: str, case_id: str, row: dict[str, Any]) -> dict[str, Any]:
    summary = _row_summary(row)
    success_seen = bool(summary["successful_candidate_observed"])
    submitted = bool(summary["submitted"])
    if summary["verdict"] == "PASS":
        status = "pass"
    elif success_seen and not submitted:
        status = "acceptance_failure"
    else:
        status = "discovery_failure"
    return {
        "run_id": run_id,
        "case_id": case_id,
        "status": status,
        "verdict": summary["verdict"],
        "submitted": submitted,
        "successful_candidate_observed": success_seen,
        "first_successful_tool_step": summary["first_successful_tool_step"],
        "unique_candidate_count": summary["unique_candidate_count"],
        "token_used": summary["token_used"],
        "checkpoint_count": _checkpoint_count(row),
        "checkpoint_guard_count": _checkpoint_guard_count(row),
        "critique_tool_count": _critique_tool_count(row),
        "check_model_call_count": _tool_call_count(row, "check_model"),
        "simulate_model_call_count": _tool_call_count(row, "simulate_model"),
        "last_failed_omc_excerpt": _failed_check_excerpt(row),
    }


def _case_classification(rows: list[dict[str, Any]]) -> str:
    pass_count = sum(1 for row in rows if row["status"] == "pass")
    success_seen_count = sum(1 for row in rows if row["successful_candidate_observed"])
    discovery_fail_count = sum(1 for row in rows if row["status"] == "discovery_failure")
    if pass_count == len(rows):
        return "stable_anchor"
    if success_seen_count == 0:
        return "stable_no_success_candidate"
    if discovery_fail_count and pass_count:
        return "discovery_unstable"
    if discovery_fail_count:
        return "mostly_discovery_failure"
    return "acceptance_or_submission_boundary"


def build_candidate_discovery_attribution(
    *,
    run_dirs: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    active_run_dirs = run_dirs or DEFAULT_RUN_DIRS
    rows_by_run = {run_id: _rows(run_dir) for run_id, run_dir in active_run_dirs.items()}
    case_ids = sorted({case_id for rows in rows_by_run.values() for case_id in rows})
    run_case_rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        per_case: list[dict[str, Any]] = []
        for run_id, rows in sorted(rows_by_run.items()):
            row = _run_case_row(run_id=run_id, case_id=case_id, row=rows.get(case_id, {}))
            per_case.append(row)
            run_case_rows.append(row)
        cases.append(
            {
                "case_id": case_id,
                "classification": _case_classification(per_case),
                "run_count": len(per_case),
                "pass_count": sum(1 for row in per_case if row["status"] == "pass"),
                "success_seen_count": sum(1 for row in per_case if row["successful_candidate_observed"]),
                "discovery_failure_count": sum(1 for row in per_case if row["status"] == "discovery_failure"),
                "acceptance_failure_count": sum(1 for row in per_case if row["status"] == "acceptance_failure"),
                "checkpoint_count": sum(int(row["checkpoint_count"]) for row in per_case),
                "checkpoint_guard_count": sum(int(row["checkpoint_guard_count"]) for row in per_case),
                "runs": per_case,
            }
        )

    discovery_failures = sum(1 for row in run_case_rows if row["status"] == "discovery_failure")
    acceptance_failures = sum(1 for row in run_case_rows if row["status"] == "acceptance_failure")
    if discovery_failures > acceptance_failures:
        decision = "candidate_discovery_is_current_bottleneck"
    elif acceptance_failures:
        decision = "candidate_acceptance_remains_bottleneck"
    else:
        decision = "no_failure_bottleneck_observed"

    summary = {
        "version": "v0.30.5",
        "status": "PASS" if run_case_rows else "REVIEW",
        "analysis_scope": "candidate_discovery_attribution",
        "run_count": len(active_run_dirs),
        "case_count": len(cases),
        "run_case_count": len(run_case_rows),
        "pass_count": sum(1 for row in run_case_rows if row["status"] == "pass"),
        "discovery_failure_count": discovery_failures,
        "acceptance_failure_count": acceptance_failures,
        "checkpoint_count": sum(int(row["checkpoint_count"]) for row in run_case_rows),
        "checkpoint_guard_count": sum(int(row["checkpoint_guard_count"]) for row in run_case_rows),
        "cases": cases,
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
