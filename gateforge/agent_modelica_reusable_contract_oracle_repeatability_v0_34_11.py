from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_methodology_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "reusable_contract_oracle_live_probe_v0_34_10_sem19_run_01",
    REPO_ROOT / "artifacts" / "reusable_contract_oracle_live_probe_v0_34_10_sem19_retry_02",
    REPO_ROOT / "artifacts" / "reusable_contract_oracle_live_probe_v0_34_10_sem19_retry_03",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "reusable_contract_oracle_repeatability_v0_34_11"


def _tool_result_contains(step: dict[str, Any], tool_name: str, needle: str) -> bool:
    for result in step.get("tool_results", []):
        if not isinstance(result, dict) or result.get("name") != tool_name:
            continue
        if needle in str(result.get("result") or ""):
            return True
    return False


def _run_row(run_dir: Path) -> dict[str, Any] | None:
    rows = load_jsonl(run_dir / "results.jsonl")
    if not rows:
        return None
    row = rows[0]
    tool_sequence = [
        str(call.get("name") or "")
        for step in row.get("steps", [])
        if isinstance(step, dict)
        for call in step.get("tool_calls", [])
        if isinstance(call, dict)
    ]
    success_seen = any(
        isinstance(step, dict)
        and (
            _tool_result_contains(step, "check_model", 'resultFile = "/workspace/')
            or _tool_result_contains(step, "simulate_model", 'resultFile = "/workspace/')
        )
        for step in row.get("steps", [])
    )
    oracle_pass_seen = any(
        isinstance(step, dict)
        and _tool_result_contains(step, "reusable_contract_oracle_diagnostic", '"contract_oracle_pass": true')
        for step in row.get("steps", [])
    )
    return {
        "run_id": run_dir.name,
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "provider_error": str(row.get("provider_error") or ""),
        "token_used": int(row.get("token_used") or 0),
        "step_count": int(row.get("step_count") or 0),
        "success_candidate_seen": success_seen,
        "oracle_pass_seen": oracle_pass_seen,
        "tool_sequence": tool_sequence,
    }


def build_reusable_contract_oracle_repeatability(
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
    pass_count = sum(1 for row in rows if row["final_verdict"] == "PASS")
    success_seen_count = sum(1 for row in rows if row["success_candidate_seen"])
    oracle_pass_count = sum(1 for row in rows if row["oracle_pass_seen"])
    success_oracle_without_submit = sum(
        1 for row in rows if row["success_candidate_seen"] and row["oracle_pass_seen"] and not row["submitted"]
    )
    provider_error_count = sum(1 for row in rows if row["provider_error"])
    if pass_count and success_oracle_without_submit:
        decision = "oracle_resolves_contract_but_submit_timing_remains_unstable"
    elif pass_count:
        decision = "oracle_contract_profile_positive_signal"
    elif oracle_pass_count:
        decision = "oracle_contract_profile_oracle_pass_without_submit"
    else:
        decision = "oracle_contract_profile_no_positive_signal"
    summary = {
        "version": "v0.34.11",
        "status": "PASS" if rows and not missing_runs else "REVIEW",
        "analysis_scope": "reusable_contract_oracle_repeatability",
        "run_count": len(rows),
        "pass_count": pass_count,
        "success_candidate_seen_count": success_seen_count,
        "oracle_pass_count": oracle_pass_count,
        "success_oracle_without_submit_count": success_oracle_without_submit,
        "provider_error_count": provider_error_count,
        "missing_runs": missing_runs,
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
