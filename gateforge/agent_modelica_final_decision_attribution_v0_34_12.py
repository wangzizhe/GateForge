from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_dyad_ab_summary_v0_29_11 import load_jsonl

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "reusable_contract_oracle_live_probe_v0_34_10_sem19_run_01",
    REPO_ROOT / "artifacts" / "reusable_contract_oracle_live_probe_v0_34_10_sem19_retry_02",
    REPO_ROOT / "artifacts" / "reusable_contract_oracle_live_probe_v0_34_10_sem19_retry_03",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "final_decision_attribution_v0_34_12"


def _tool_result_text(step: dict[str, Any], tool_name: str) -> str:
    return "\n".join(
        str(result.get("result") or "")
        for result in step.get("tool_results", [])
        if isinstance(result, dict) and result.get("name") == tool_name
    )


def _tool_names(step: dict[str, Any]) -> list[str]:
    return [
        str(call.get("name") or "")
        for call in step.get("tool_calls", [])
        if isinstance(call, dict)
    ]


def _has_success_evidence(step: dict[str, Any]) -> bool:
    check_text = _tool_result_text(step, "check_model")
    simulate_text = _tool_result_text(step, "simulate_model")
    return 'resultFile = "/workspace/' in check_text or 'resultFile = "/workspace/' in simulate_text


def _has_oracle_pass(step: dict[str, Any]) -> bool:
    return '"contract_oracle_pass": true' in _tool_result_text(step, "reusable_contract_oracle_diagnostic")


def _classify_run(row: dict[str, Any], steps: list[dict[str, Any]]) -> str:
    submitted = bool(row.get("submitted"))
    success_steps = [int(step.get("step") or 0) for step in steps if _has_success_evidence(step)]
    oracle_steps = [int(step.get("step") or 0) for step in steps if _has_oracle_pass(step)]
    submit_steps = [
        int(step.get("step") or 0)
        for step in steps
        if "submit_final" in _tool_names(step)
    ]
    if submitted:
        if oracle_steps:
            return "submitted_after_success_and_oracle_pass"
        return "submitted_after_success_without_oracle"
    if not success_steps:
        return "no_success_candidate_seen"
    if not oracle_steps:
        return "success_candidate_seen_without_oracle_call"
    last_oracle = max(oracle_steps)
    later_success = any(step > last_oracle for step in success_steps)
    if later_success:
        return "oracle_pass_then_continued_candidate_search_until_limit"
    if not submit_steps:
        return "oracle_pass_without_submit"
    return "unsubmitted_after_success"


def _run_row(run_dir: Path) -> dict[str, Any] | None:
    rows = load_jsonl(run_dir / "results.jsonl")
    if not rows:
        return None
    row = rows[0]
    steps = [step for step in row.get("steps", []) if isinstance(step, dict)]
    success_steps = [int(step.get("step") or 0) for step in steps if _has_success_evidence(step)]
    oracle_pass_steps = [int(step.get("step") or 0) for step in steps if _has_oracle_pass(step)]
    submit_steps = [
        int(step.get("step") or 0)
        for step in steps
        if "submit_final" in _tool_names(step)
    ]
    last_tool_step = steps[-1] if steps else {}
    return {
        "run_id": run_dir.name,
        "case_id": str(row.get("case_id") or ""),
        "final_verdict": str(row.get("final_verdict") or ""),
        "submitted": bool(row.get("submitted")),
        "provider_error": str(row.get("provider_error") or ""),
        "step_count": int(row.get("step_count") or 0),
        "token_used": int(row.get("token_used") or 0),
        "success_evidence_steps": success_steps,
        "oracle_pass_steps": oracle_pass_steps,
        "submit_steps": submit_steps,
        "last_tool_names": _tool_names(last_tool_step),
        "last_step_has_success_evidence": bool(last_tool_step) and _has_success_evidence(last_tool_step),
        "last_step_text_excerpt": str(last_tool_step.get("text") or "")[:500],
        "failure_class": _classify_run(row, steps),
    }


def build_final_decision_attribution(
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
    success_without_submit_count = sum(
        1 for row in rows if row["success_evidence_steps"] and not row["submitted"]
    )
    oracle_pass_without_submit_count = sum(
        1 for row in rows if row["oracle_pass_steps"] and not row["submitted"]
    )
    if oracle_pass_without_submit_count:
        decision = "final_decision_instability_after_oracle_pass"
    elif success_without_submit_count:
        decision = "final_decision_instability_after_success_evidence"
    else:
        decision = "final_decision_path_stable_in_observed_runs"
    summary = {
        "version": "v0.34.12",
        "status": "PASS" if rows and not missing_runs else "REVIEW",
        "analysis_scope": "final_decision_attribution_after_success_evidence",
        "run_count": len(rows),
        "missing_runs": missing_runs,
        "pass_count": sum(1 for row in rows if row["final_verdict"] == "PASS"),
        "submitted_count": sum(1 for row in rows if row["submitted"]),
        "success_without_submit_count": success_without_submit_count,
        "oracle_pass_without_submit_count": oracle_pass_without_submit_count,
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
