from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_modelica_repair_quality_score_v1 import compute_repair_quality_breakdown


SCHEMA_VERSION = "agent_modelica_experience_writer_v1"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attempts(run_result: dict) -> list[dict]:
    attempts = run_result.get("attempts") if isinstance(run_result.get("attempts"), list) else []
    return [row for row in attempts if isinstance(row, dict)]


def _bucket_rank(bucket: str) -> int:
    text = str(bucket or "").strip().lower()
    if not text:
        return 1
    if text in {"passed", "pass", "success", "resolved", "none"}:
        return 5
    if "retry_pending" in text:
        return 1
    if any(token in text for token in ("behavior", "semantic_regression", "simulate_error", "scenario_switch", "transient", "steady_state", "mode_transition")):
        return 4
    if any(token in text for token in ("model_check_error", "script_parse_error", "compile", "check", "parse")):
        return 3
    return 2


def classify_action_contribution(*, failure_bucket_before: str, failure_bucket_after: str) -> str:
    before = str(failure_bucket_before or "").strip().lower()
    after = str(failure_bucket_after or "").strip().lower()
    if after in {"passed", "pass", "success", "resolved", "none"}:
        return "advancing"
    before_rank = _bucket_rank(before)
    after_rank = _bucket_rank(after)
    if after_rank > before_rank:
        return "advancing"
    if after_rank < before_rank:
        return "regressing"
    return "neutral"


def _terminal_failure_bucket(run_result: dict, last_attempt: dict | None) -> str:
    if bool(run_result.get("check_model_pass")) and bool(run_result.get("simulate_pass")) and bool(run_result.get("physics_contract_pass")) and bool(run_result.get("regression_pass")):
        return "passed"
    for key in ("current_fail_bucket", "contract_fail_bucket", "simulate_error_message", "compile_error", "error_message"):
        value = str(run_result.get(key) or "").strip()
        if value:
            return value
    if isinstance(last_attempt, dict):
        for key in ("current_fail_bucket", "observed_failure_type", "reason"):
            value = str(last_attempt.get(key) or "").strip()
            if value:
                return value
    return "unknown"


def _extract_applied_rule_rows(attempt: dict) -> list[dict]:
    rows: list[dict] = []
    for field_name, value in attempt.items():
        if not isinstance(value, dict):
            continue
        if not bool(value.get("applied")):
            continue
        action_key = str(value.get("action_key") or "").strip()
        rule_id = str(value.get("rule_id") or "").strip()
        if not action_key and not rule_id:
            continue
        rows.append(
            {
                "attempt_field": field_name,
                "rule_id": rule_id,
                "action_key": action_key,
                "rule_tier": str(value.get("rule_tier") or ""),
                "replay_eligible": bool(value.get("replay_eligible")),
                "failure_bucket_before": str(value.get("failure_bucket_before") or ""),
                "failure_bucket_after": str(value.get("failure_bucket_after") or ""),
                "audit_reason": str(value.get("reason") or ""),
            }
        )
    return rows


def build_action_contribution_rows(run_result: dict) -> list[dict]:
    attempts = _attempts(run_result)
    rows: list[dict] = []
    for idx, attempt in enumerate(attempts):
        next_attempt = attempts[idx + 1] if idx + 1 < len(attempts) else None
        terminal_bucket = _terminal_failure_bucket(run_result, attempts[-1] if attempts else None)
        next_bucket = ""
        if isinstance(next_attempt, dict):
            next_bucket = str(next_attempt.get("current_fail_bucket") or next_attempt.get("observed_failure_type") or next_attempt.get("reason") or "").strip()
        if not next_bucket:
            next_bucket = terminal_bucket
        for action in _extract_applied_rule_rows(attempt):
            before = str(action.get("failure_bucket_before") or attempt.get("current_fail_bucket") or attempt.get("observed_failure_type") or run_result.get("failure_type") or "").strip()
            after = str(next_bucket or action.get("failure_bucket_after") or "").strip()
            rows.append(
                {
                    "task_id": str(run_result.get("task_id") or ""),
                    "failure_type": str(run_result.get("failure_type") or ""),
                    "round_idx": int(attempt.get("round") or (idx + 1)),
                    "attempt_field": str(action.get("attempt_field") or ""),
                    "rule_id": str(action.get("rule_id") or ""),
                    "action_key": str(action.get("action_key") or ""),
                    "rule_tier": str(action.get("rule_tier") or ""),
                    "replay_eligible": bool(action.get("replay_eligible")),
                    "failure_bucket_before": before,
                    "failure_bucket_after": after,
                    "contribution": classify_action_contribution(
                        failure_bucket_before=before,
                        failure_bucket_after=after,
                    ),
                    "audit_reason": str(action.get("audit_reason") or ""),
                }
            )
    return rows


def build_experience_record(run_result: dict) -> dict:
    quality = compute_repair_quality_breakdown(run_result)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "task_id": str(run_result.get("task_id") or ""),
        "failure_type": str(run_result.get("failure_type") or ""),
        "executor_status": str(run_result.get("executor_status") or ""),
        "repair_quality_score": float(quality.get("repair_quality_score") or 0.0),
        "repair_quality_breakdown": quality,
        "action_contributions": build_action_contribution_rows(run_result),
    }
