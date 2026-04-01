from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_branch_switch_family_spec_v0_3_7 import (
    BASELINE_LEVER_NAME,
    BASELINE_PROTOCOL_VERSION,
    BASELINE_REFERENCE_VERSION,
    FAMILY_ID,
)


SCHEMA_VERSION = "agent_modelica_branch_switch_taskset_v0_3_7"
DEFAULT_SOURCE_TASKSET = "artifacts/agent_modelica_v0_3_6_recommended_taskset_current/taskset.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_branch_switch_taskset_v0_3_7"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _mutation_rows(task: dict) -> list[dict]:
    mutation_spec = task.get("mutation_spec")
    if not isinstance(mutation_spec, dict):
        return []
    hidden = mutation_spec.get("hidden_base")
    if not isinstance(hidden, dict):
        return []
    audit = hidden.get("audit")
    if not isinstance(audit, dict):
        return []
    mutations = audit.get("mutations")
    if isinstance(mutations, list):
        return [row for row in mutations if isinstance(row, dict)]
    return []


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


def build_branch_candidates(task: dict) -> list[dict]:
    mutations = _mutation_rows(task)
    if len(mutations) < 2:
        return []
    first = mutations[0]
    second = mutations[1]
    first_name = _norm(first.get("param_name"))
    second_name = _norm(second.get("param_name"))
    if not first_name or not second_name:
        return []
    return [
        {
            "branch_id": f"continue_on_{first_name}",
            "branch_kind": "continue_current_line",
            "trigger_signal": "stalled_search_after_progress",
            "viability_status": "plausible_but_stalled",
            "supporting_parameters": [first_name],
        },
        {
            "branch_id": f"switch_to_{second_name}",
            "branch_kind": "branch_switch_candidate",
            "trigger_signal": "stalled_search_after_progress",
            "viability_status": "preferred_after_stall",
            "supporting_parameters": [second_name],
        },
    ]


def build_branch_switch_task(task: dict) -> dict | None:
    if _norm(task.get("hidden_base_operator")) != "paired_value_collapse":
        return None
    branches = build_branch_candidates(task)
    if len(branches) < 2:
        return None
    mutations = _mutation_rows(task)
    first_name = _norm(mutations[0].get("param_name"))
    second_name = _norm(mutations[1].get("param_name"))
    return {
        **task,
        "v0_3_7_family_id": FAMILY_ID,
        "required_entry_bucket": "stalled_search_after_progress",
        "residual_hidden_parameters": [first_name, second_name],
        "current_branch": f"continue_on_{first_name}",
        "preferred_branch": f"switch_to_{second_name}",
        "candidate_branches": branches,
        "expected_post_restore_failure_buckets": [
            "stalled_search_after_progress",
            "wrong_branch_after_restore",
        ],
        "branch_switch_design": {
            "mainline_problem": "first_progress_then_stall_then_branch_switch",
            "current_branch_param": first_name,
            "preferred_branch_param": second_name,
        },
        "baseline_measurement_protocol": _baseline_measurement_protocol(),
    }


def build_branch_switch_taskset(
    *,
    source_taskset_path: str = DEFAULT_SOURCE_TASKSET,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(source_taskset_path)
    tasks = _task_rows(payload)
    converted = []
    skipped = []
    for task in tasks:
        converted_task = build_branch_switch_task(task)
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
    lines = [
        "# v0.3.7 Branch-Switch Taskset",
        "",
        f"- status: `{summary.get('status')}`",
        f"- family_id: `{summary.get('family_id')}`",
        f"- task_count: `{summary.get('task_count')}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.7 branch-switch-after-stall candidate taskset.")
    parser.add_argument("--source-taskset", default=DEFAULT_SOURCE_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_branch_switch_taskset(
        source_taskset_path=str(args.source_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))


if __name__ == "__main__":
    main()
