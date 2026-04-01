from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_same_branch_continuity_family_spec_v0_3_10 import (
    BASELINE_LEVER_NAME,
    BASELINE_PROTOCOL_VERSION,
    BASELINE_REFERENCE_VERSION,
    FAMILY_ID,
    SOURCE_BUCKET,
)


SCHEMA_VERSION = "agent_modelica_same_branch_continuity_taskset_v0_3_10"
DEFAULT_SOURCE_CLASSIFIER_SUMMARY = "artifacts/agent_modelica_v0_3_9_absorbed_success_classifier_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_same_branch_continuity_taskset_v0_3_10"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _rows(payload: dict) -> list[dict]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _baseline_measurement_protocol() -> dict:
    return {
        "protocol_version": BASELINE_PROTOCOL_VERSION,
        "baseline_lever_name": BASELINE_LEVER_NAME,
        "baseline_reference_version": BASELINE_REFERENCE_VERSION,
        "profile_id": "repair-executor",
        "max_rounds": 6,
        "timeout_sec": 600,
        "simulate_stop_time": 10.0,
        "simulate_intervals": 500,
        "enabled_policy_flags": {
            "source_restore_allowed": True,
            "deterministic_rules_enabled": True,
            "replay_enabled": True,
            "planner_injection_enabled": True,
            "behavioral_contract_required": False,
            "allow_baseline_single_sweep": True,
            "allow_new_multistep_policy": False,
            "allow_branch_switch_replan_policy": False,
            "allow_same_branch_continuity_policy": False,
        },
    }


def build_same_branch_continuity_task(task: dict) -> dict | None:
    if _norm(task.get("absorbed_success_primary_bucket")) != SOURCE_BUCKET:
        return None
    sequence = task.get("detected_branch_sequence")
    sequence = [_norm(item) for item in sequence if _norm(item)] if isinstance(sequence, list) else []
    selected_branch = _norm(task.get("selected_branch"))
    current_branch = _norm(task.get("current_branch"))
    candidate_branches = task.get("candidate_next_branches") or task.get("candidate_branches")
    if not selected_branch or not current_branch or not sequence:
        return None
    if len(set(sequence)) != 1:
        return None
    if sequence[0] != selected_branch:
        return None
    if current_branch != selected_branch:
        return None
    if not isinstance(candidate_branches, list) or not candidate_branches:
        return None
    continuity_design = {
        "mainline_problem": "same_branch_continuation_after_partial_progress",
        "required_entry_state": "partial_progress_on_same_branch",
        "required_success_mode": "success_after_same_branch_continuation",
        "forbidden_success_mode": "success_after_branch_switch",
        "current_branch": current_branch,
        "selected_branch": selected_branch,
        "source_primary_bucket": SOURCE_BUCKET,
    }
    return {
        **task,
        "v0_3_10_family_id": FAMILY_ID,
        "source_primary_bucket": SOURCE_BUCKET,
        "same_branch_continuity_design": continuity_design,
        "branch_identity_continuous": True,
        "same_branch_refinement_event_count": 0,
        "previous_successful_same_branch_step": "",
        "continuation_refinement_target": "",
        "continuation_outcome_state": "not_yet_refreshed",
        "baseline_measurement_protocol": _baseline_measurement_protocol(),
    }


def build_same_branch_continuity_taskset(
    *,
    source_classifier_summary_path: str = DEFAULT_SOURCE_CLASSIFIER_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(source_classifier_summary_path)
    rows = _rows(payload)
    converted = []
    skipped = []
    for task in rows:
        converted_task = build_same_branch_continuity_task(task)
        if converted_task is None:
            skipped.append(_norm(task.get("item_id") or task.get("task_id")))
            continue
        converted.append(converted_task)

    out_root = Path(out_dir)
    for task in converted:
        _write_json(out_root / "tasks" / f"{task['task_id']}.json", task)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if converted else "EMPTY",
        "source_classifier_summary_path": str(Path(source_classifier_summary_path).resolve()) if Path(source_classifier_summary_path).exists() else str(source_classifier_summary_path),
        "family_id": FAMILY_ID,
        "source_primary_bucket": SOURCE_BUCKET,
        "task_count": len(converted),
        "task_ids": [str(task.get("task_id") or "") for task in converted],
        "skipped_task_ids": [row for row in skipped if row],
        "baseline_measurement_protocol": _baseline_measurement_protocol(),
        "tasks": converted,
    }
    _write_json(out_root / "taskset.json", summary)
    _write_text(out_root / "summary.md", render_markdown(summary))
    return summary


def render_markdown(summary: dict) -> str:
    return "\n".join(
        [
            "# v0.3.10 Same-Branch Continuity Taskset",
            "",
            f"- status: `{summary.get('status')}`",
            f"- family_id: `{summary.get('family_id')}`",
            f"- source_primary_bucket: `{summary.get('source_primary_bucket')}`",
            f"- task_count: `{summary.get('task_count')}`",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.10 same-branch continuity candidate taskset.")
    parser.add_argument("--source-classifier-summary", default=DEFAULT_SOURCE_CLASSIFIER_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_same_branch_continuity_taskset(
        source_classifier_summary_path=str(args.source_classifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))


if __name__ == "__main__":
    main()
