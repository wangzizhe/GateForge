from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_14_step_experience_common import (
    STEP_SCHEMA_VERSION,
    action_type_from_row,
    bool_or_none,
    norm,
    now_utc,
    residual_signal_cluster,
)


SCHEMA_VERSION = "agent_modelica_v0_3_14_authority_trace_extraction"


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _manifest_rows(manifest_payload: dict, *, include_eval: bool = False) -> list[dict]:
    rows: list[dict] = []
    for section_name in ("runtime", "initialization"):
        section = manifest_payload.get(section_name) if isinstance(manifest_payload.get(section_name), dict) else {}
        rows.extend([row for row in (section.get("experience_sources") or []) if isinstance(row, dict)])
        if include_eval:
            rows.extend([row for row in (section.get("eval_tasks") or []) if isinstance(row, dict)])
    return rows


def _failure_rows(manifest_payload: dict) -> list[dict]:
    failure_bank = manifest_payload.get("failure_bank") if isinstance(manifest_payload.get("failure_bank"), dict) else {}
    rows = [row for row in (failure_bank.get("runtime_failures") or []) if isinstance(row, dict)]
    rows.extend([row for row in (failure_bank.get("initialization_failures") or []) if isinstance(row, dict)])
    return rows


def _extract_applied_actions(attempt: dict) -> list[dict]:
    rows: list[dict] = []
    for field_name, value in attempt.items():
        if not isinstance(value, dict):
            continue
        if not bool(value.get("applied")):
            continue
        rows.append(
            {
                "attempt_field": field_name,
                "rule_id": norm(value.get("rule_id")),
                "action_key": norm(value.get("action_key")),
                "rule_tier": norm(value.get("rule_tier")),
                "replay_eligible": bool(value.get("replay_eligible")),
                "failure_bucket_before": norm(value.get("failure_bucket_before")),
                "failure_bucket_after": norm(value.get("failure_bucket_after")),
            }
        )
    return rows


def _after_bool(current: dict, next_attempt: dict | None, run_result: dict, key: str) -> bool | None:
    if isinstance(next_attempt, dict):
        value = bool_or_none(next_attempt.get(key))
        if value is not None:
            return value
    return bool_or_none(run_result.get(key))


def _step_outcome(*, progress_labels: list[str], terminal_outcome: str, is_last_action_round: bool) -> str:
    if progress_labels:
        return "advancing"
    if terminal_outcome == "pass" and is_last_action_round:
        return "advancing"
    if terminal_outcome == "fail" and is_last_action_round:
        return "dead_end"
    return "non_progress"


def extract_step_records(run_result: dict, *, source_entry: dict) -> list[dict]:
    attempts = run_result.get("attempts") if isinstance(run_result.get("attempts"), list) else []
    valid_attempts = [row for row in attempts if isinstance(row, dict)]
    terminal_outcome = "pass" if norm(run_result.get("executor_status")).upper() == "PASS" else "fail"
    planner_event_count = int(((run_result.get("executor_runtime_hygiene") or {}).get("planner_event_count") or 0))
    rows: list[dict] = []
    last_action_round = 0
    attempts_with_actions: list[tuple[int, dict, list[dict]]] = []
    for idx, attempt in enumerate(valid_attempts):
        actions = _extract_applied_actions(attempt)
        if actions:
            attempts_with_actions.append((idx, attempt, actions))
            last_action_round = int(attempt.get("round") or idx + 1)

    for idx, attempt, actions in attempts_with_actions:
        next_attempt = valid_attempts[idx + 1] if idx + 1 < len(valid_attempts) else None
        diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
        stage_subtype = norm(diagnostic.get("dominant_stage_subtype") or run_result.get("dominant_stage_subtype"))
        error_subtype = norm(diagnostic.get("error_subtype"))
        observed_failure_type = norm(attempt.get("observed_failure_type") or run_result.get("failure_type"))
        reason = norm(attempt.get("reason"))
        cluster = residual_signal_cluster(
            dominant_stage_subtype=stage_subtype,
            error_subtype=error_subtype,
            observed_failure_type=observed_failure_type,
            reason=reason,
        )
        current_check = bool_or_none(attempt.get("check_model_pass"))
        current_simulate = bool_or_none(attempt.get("simulate_pass"))
        after_check = _after_bool(attempt, next_attempt, run_result, "check_model_pass")
        after_simulate = _after_bool(attempt, next_attempt, run_result, "simulate_pass")
        progress_labels: list[str] = []
        if current_check is False and after_check is True:
            progress_labels.append("check_model_recovery")
        if current_simulate is False and after_simulate is True:
            progress_labels.append("simulate_recovery")
        next_cluster = ""
        if isinstance(next_attempt, dict):
            next_diag = next_attempt.get("diagnostic_ir") if isinstance(next_attempt.get("diagnostic_ir"), dict) else {}
            next_cluster = residual_signal_cluster(
                dominant_stage_subtype=norm(next_diag.get("dominant_stage_subtype")),
                error_subtype=norm(next_diag.get("error_subtype")),
                observed_failure_type=norm(next_attempt.get("observed_failure_type")),
                reason=norm(next_attempt.get("reason")),
            )
        elif terminal_outcome == "pass":
            next_cluster = "resolved"
        if next_cluster and next_cluster not in {cluster, "unknown_residual_signal"}:
            progress_labels.append("residual_transition")
        if terminal_outcome == "pass" and int(attempt.get("round") or idx + 1) == last_action_round:
            progress_labels.append("terminal_success")
        seen_labels = []
        for label in progress_labels:
            if label not in seen_labels:
                seen_labels.append(label)
        progress_labels = seen_labels
        for action in actions:
            action_type = action_type_from_row(
                attempt_field=norm(action.get("attempt_field")),
                action_key=norm(action.get("action_key")),
                rule_id=norm(action.get("rule_id")),
            )
            rows.append(
                {
                    "schema_version": STEP_SCHEMA_VERSION,
                    "generated_at_utc": now_utc(),
                    "task_id": norm(source_entry.get("task_id")),
                    "source_task_id": norm(source_entry.get("source_task_id")),
                    "lane_name": norm(source_entry.get("lane_name")),
                    "trace_role": norm(source_entry.get("role")),
                    "result_json_path": norm(source_entry.get("result_json_path")),
                    "round_idx": int(attempt.get("round") or idx + 1),
                    "dominant_stage_subtype": stage_subtype,
                    "error_subtype": error_subtype,
                    "observed_failure_type": observed_failure_type,
                    "reason": reason,
                    "residual_signal_cluster": cluster,
                    "branch_identity": "",
                    "action_type": action_type,
                    "action_key": norm(action.get("action_key")),
                    "rule_id": norm(action.get("rule_id")),
                    "rule_tier": norm(action.get("rule_tier")),
                    "attempt_field": norm(action.get("attempt_field")),
                    "replay_eligible": bool(action.get("replay_eligible") or norm(action.get("rule_id")) or norm(action.get("action_key")) or action_type),
                    "resolution_path": norm(run_result.get("resolution_path")),
                    "planner_event_count": planner_event_count,
                    "rounds_used": int(run_result.get("rounds_used") or len(valid_attempts)),
                    "terminal_outcome": terminal_outcome,
                    "observed_progress": progress_labels,
                    "step_outcome": _step_outcome(
                        progress_labels=progress_labels,
                        terminal_outcome=terminal_outcome,
                        is_last_action_round=int(attempt.get("round") or idx + 1) == last_action_round,
                    ),
                }
            )
    return rows


def _summary(step_records: list[dict], failure_bank: list[dict]) -> dict:
    by_lane: dict[str, int] = {}
    by_cluster: dict[str, int] = {}
    by_action_type: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for row in step_records:
        lane = norm(row.get("lane_name")) or "unknown"
        cluster = norm(row.get("residual_signal_cluster")) or "unknown"
        action_type = norm(row.get("action_type")) or "unknown"
        outcome = norm(row.get("step_outcome")) or "unknown"
        by_lane[lane] = by_lane.get(lane, 0) + 1
        by_cluster[cluster] = by_cluster.get(cluster, 0) + 1
        by_action_type[action_type] = by_action_type.get(action_type, 0) + 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if step_records else "EMPTY",
        "step_record_count": len(step_records),
        "failure_bank_step_count": len(failure_bank),
        "lane_distribution": by_lane,
        "residual_signal_cluster_distribution": by_cluster,
        "action_type_distribution": by_action_type,
        "step_outcome_distribution": by_outcome,
    }


def build_authority_trace_extraction(*, manifest_path: str, out_dir: str) -> dict:
    manifest = _load_json(manifest_path)
    train_rows = _manifest_rows(manifest, include_eval=False)
    failure_rows = _failure_rows(manifest)
    experience_steps: list[dict] = []
    failure_steps: list[dict] = []
    for entry in train_rows:
        detail = _load_json(entry.get("result_json_path") or "")
        experience_steps.extend(extract_step_records(detail, source_entry=entry))
    for entry in failure_rows:
        detail = _load_json(entry.get("result_json_path") or "")
        failure_steps.extend(extract_step_records(detail, source_entry=entry))
    store = {
        "schema_version": "agent_modelica_v0_3_14_experience_store",
        "generated_at_utc": now_utc(),
        "source_manifest_path": str(Path(manifest_path).resolve()) if Path(manifest_path).exists() else str(manifest_path),
        "step_records": experience_steps,
    }
    failure_bank = {
        "schema_version": "agent_modelica_v0_3_14_failure_bank",
        "generated_at_utc": now_utc(),
        "source_manifest_path": str(Path(manifest_path).resolve()) if Path(manifest_path).exists() else str(manifest_path),
        "step_records": failure_steps,
    }
    summary = _summary(experience_steps, failure_steps)
    out_root = Path(out_dir)
    _write_json(out_root / "experience_store.json", store)
    _write_json(out_root / "failure_bank.json", failure_bank)
    _write_json(out_root / "summary.json", summary)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.14 Authority Trace Extraction",
                "",
                f"- status: `{summary.get('status')}`",
                f"- step_record_count: `{summary.get('step_record_count')}`",
                f"- failure_bank_step_count: `{summary.get('failure_bank_step_count')}`",
                "",
            ]
        ),
    )
    return {
        "summary": summary,
        "experience_store_path": str((out_root / "experience_store.json").resolve()),
        "failure_bank_path": str((out_root / "failure_bank.json").resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract v0.3.14 authority step-level experience and failure bank.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    payload = build_authority_trace_extraction(manifest_path=str(args.manifest), out_dir=str(args.out_dir))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "step_record_count": summary.get("step_record_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
