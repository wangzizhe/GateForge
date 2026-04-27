from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from .agent_modelica_deepseek_slice_review_v0_27_2 import classify_omc_feedback, load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SLICE_PLAN = REPO_ROOT / "artifacts" / "benchmark_slice_plan_v0_27_9" / "slice_plan.jsonl"
DEFAULT_RESULTS = REPO_ROOT / "artifacts" / "role_separated_live_slice_v0_27_10" / "results.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "capability_slice_audit_v0_27_11"


def _plans_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("candidate_id") or ""): row for row in rows if row.get("candidate_id")}


def _feedback_sequence(result: dict[str, Any]) -> list[str]:
    sequence: list[str] = []
    for attempt in result.get("attempts", []):
        if not isinstance(attempt, dict) or not attempt.get("llm_called"):
            continue
        sequence.append(
            classify_omc_feedback(
                str(attempt.get("raw_omc_after_patch") or ""),
                check_pass=attempt.get("check_pass_after_patch"),
            )
        )
    return sequence


def _final_round_stalled(result: dict[str, Any]) -> bool:
    attempts = [attempt for attempt in result.get("attempts", []) if isinstance(attempt, dict)]
    if not attempts:
        return False
    last = attempts[-1]
    return bool(last.get("llm_called")) and bool(last.get("patched_text_present")) and not bool(last.get("model_changed"))


def audit_capability_slice(
    *,
    slice_plan_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    plans = _plans_by_id([row for row in slice_plan_rows if str(row.get("slice_role") or "") == "capability_baseline"])
    audited: list[dict[str, Any]] = []
    for result in result_rows:
        case_id = str(result.get("case_id") or "")
        if case_id not in plans:
            continue
        sequence = _feedback_sequence(result)
        terminal = sequence[-1] if sequence else "no_repair_attempt"
        final_verdict = str(result.get("final_verdict") or "")
        stalled = _final_round_stalled(result)
        audited.append(
            {
                "case_id": case_id,
                "family": str(plans[case_id].get("family") or ""),
                "repeatability_class": str(plans[case_id].get("repeatability_class") or ""),
                "final_verdict": final_verdict,
                "repair_round_count": int(result.get("repair_round_count") or 0),
                "true_multi_turn": bool(result.get("true_multi_turn")),
                "feedback_sequence": sequence,
                "terminal_feedback": terminal,
                "final_round_stalled": stalled,
                "provider_error": any(str(attempt.get("llm_error") or "") for attempt in result.get("attempts", []) if isinstance(attempt, dict)),
                "current_harness_baseline_failure_signal": (
                    final_verdict != "PASS"
                    and terminal == "underdetermined_system"
                    and stalled
                ),
            }
        )
    pass_count = sum(1 for row in audited if row["final_verdict"] == "PASS")
    failure_signal_count = sum(1 for row in audited if row["current_harness_baseline_failure_signal"])
    terminal_counts = Counter(row["terminal_feedback"] for row in audited)
    summary = {
        "version": "v0.27.11",
        "status": "PASS" if audited else "REVIEW",
        "analysis_scope": "capability_slice_current_harness_audit",
        "slice_plan_artifact": str(DEFAULT_SLICE_PLAN.relative_to(REPO_ROOT)),
        "result_artifact": str(DEFAULT_RESULTS.relative_to(REPO_ROOT)),
        "provider": str(os.getenv("LLM_PROVIDER") or "deepseek").strip(),
        "model_profile": str(os.getenv("LLM_MODEL") or "deepseek-v4-flash").strip(),
        "run_mode": "raw_only",
        "audited_case_count": len(audited),
        "pass_count": pass_count,
        "failure_signal_count": failure_signal_count,
        "terminal_feedback_distribution": dict(sorted(terminal_counts.items())),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "demote_capability_baseline_for_current_deepseek_harness"
            if audited and pass_count == 0 and failure_signal_count == len(audited)
            else "capability_baseline_status_needs_more_evidence"
        ),
        "next_focus": "add_provider_harness_role_overrides_before_more_live_runs",
    }
    return audited, summary


def run_capability_slice_audit(
    *,
    slice_plan_path: Path = DEFAULT_SLICE_PLAN,
    results_path: Path = DEFAULT_RESULTS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    cases, summary = audit_capability_slice(
        slice_plan_rows=load_jsonl(slice_plan_path),
        result_rows=load_jsonl(results_path),
    )
    write_outputs(out_dir=out_dir, summary=summary, cases=cases)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "case_audits.jsonl").open("w", encoding="utf-8") as fh:
        for row in cases:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
