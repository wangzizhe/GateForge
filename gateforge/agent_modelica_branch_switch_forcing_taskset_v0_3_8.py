from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_branch_switch_forcing_family_spec_v0_3_8 import (
    BASELINE_LEVER_NAME,
    BASELINE_PROTOCOL_VERSION,
    BASELINE_REFERENCE_VERSION,
    FAMILY_ID,
)


SCHEMA_VERSION = "agent_modelica_branch_switch_forcing_taskset_v0_3_8"
DEFAULT_SOURCE_TASKSET = "artifacts/agent_modelica_branch_switch_taskset_v0_3_7_current/taskset.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_branch_switch_forcing_taskset_v0_3_8"


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


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
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
        },
    }


def build_branch_switch_forcing_task(task: dict) -> dict | None:
    if _norm(task.get("hidden_base_operator")) != "paired_value_collapse":
        return None
    branches = task.get("candidate_branches")
    if not isinstance(branches, list) or len(branches) < 2:
        return None
    current_branch = _norm(task.get("current_branch"))
    preferred_branch = _norm(task.get("preferred_branch"))
    if not current_branch or not preferred_branch or current_branch == preferred_branch:
        return None
    design = {
        "mainline_problem": "explicit_branch_switch_after_stalled_progress",
        "required_entry_state": "stalled_search_after_progress",
        "wrong_branch_outcome": "wrong_branch_after_restore",
        "success_mode_target": "success_after_branch_switch",
        "silent_success_forbidden": True,
        "branch_order": [current_branch, preferred_branch],
        "current_branch_param": _norm((task.get("branch_switch_design") or {}).get("current_branch_param")),
        "preferred_branch_param": _norm((task.get("branch_switch_design") or {}).get("preferred_branch_param")),
    }
    return {
        **task,
        "v0_3_8_family_id": FAMILY_ID,
        "required_entry_bucket": "stalled_search_after_progress",
        "branch_forcing_design": design,
        "baseline_measurement_protocol": _baseline_measurement_protocol(),
    }


def build_branch_switch_forcing_taskset(
    *,
    source_taskset_path: str = DEFAULT_SOURCE_TASKSET,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(source_taskset_path)
    tasks = _task_rows(payload)
    converted = []
    skipped = []
    for task in tasks:
        converted_task = build_branch_switch_forcing_task(task)
        if converted_task is None:
            skipped.append(_norm(task.get("task_id")))
            continue
        converted.append(converted_task)

    out_root = Path(out_dir)
    for task in converted:
        _write_json(out_root / "tasks" / f"{task['task_id']}.json", task)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if converted else "EMPTY",
        "source_taskset_path": str(Path(source_taskset_path).resolve()) if Path(source_taskset_path).exists() else str(source_taskset_path),
        "family_id": FAMILY_ID,
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
            "# v0.3.8 Branch-Switch Forcing Taskset",
            "",
            f"- status: `{summary.get('status')}`",
            f"- family_id: `{summary.get('family_id')}`",
            f"- task_count: `{summary.get('task_count')}`",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.8 branch-switch forcing candidate taskset.")
    parser.add_argument("--source-taskset", default=DEFAULT_SOURCE_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_branch_switch_forcing_taskset(
        source_taskset_path=str(args.source_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))


if __name__ == "__main__":
    main()
