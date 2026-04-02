from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_12_one_shot_taskset"
DEFAULT_LEGACY_TASKSET = "artifacts/agent_modelica_same_branch_continuity_taskset_v0_3_10_current/taskset.json"
DEFAULT_EXPANSION_SOURCE_TASKSET = "artifacts/agent_modelica_post_restore_taskset_v0_3_6_current/taskset.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_12_one_shot_taskset"
FAMILY_ID = "same_branch_one_shot_after_partial_progress"
SOURCE_BUCKET = "single_branch_resolution_without_true_stall"
BASELINE_PROTOCOL_VERSION = "v0_3_12_one_shot_baseline_authority_v1"
BASELINE_LEVER_NAME = "same_branch_one_shot_or_accidental_success"
BASELINE_REFERENCE_VERSION = "v0.3.10"
EXPANSION_OPERATOR = "paired_value_bias_shift"


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


def _mutation_rows(task: dict) -> list[dict]:
    hidden = (task.get("mutation_spec") or {}).get("hidden_base")
    audit = hidden.get("audit") if isinstance(hidden, dict) else None
    rows = audit.get("mutations") if isinstance(audit, dict) else None
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


def _build_branch_candidates(first_name: str, second_name: str) -> list[dict]:
    return [
        {
            "branch_id": f"continue_on_{first_name}",
            "branch_kind": "continue_current_line",
            "trigger_signal": "single_branch_resolution_without_true_stall",
            "viability_status": "same_branch_mainline_probe",
            "supporting_parameters": [first_name],
        },
        {
            "branch_id": f"switch_to_{second_name}",
            "branch_kind": "alternate_branch_candidate",
            "trigger_signal": "single_branch_resolution_without_true_stall",
            "viability_status": "contrast_branch_probe",
            "supporting_parameters": [second_name],
        },
    ]


def build_v0_3_12_legacy_task(task: dict) -> dict | None:
    task_id = _norm(task.get("task_id"))
    current_branch = _norm(task.get("current_branch"))
    selected_branch = _norm(task.get("selected_branch") or current_branch)
    sequence = task.get("detected_branch_sequence")
    sequence = [_norm(item) for item in sequence if _norm(item)] if isinstance(sequence, list) else []
    if not task_id or not current_branch or selected_branch != current_branch or not sequence:
        return None
    return {
        **task,
        "v0_3_12_family_id": FAMILY_ID,
        "source_primary_bucket": SOURCE_BUCKET,
        "sample_source_mode": "legacy_v0_3_10_admitted_lane",
        "selected_branch": current_branch,
        "baseline_measurement_protocol": _baseline_measurement_protocol(),
        "v0_3_12_one_shot_design": {
            "mainline_problem": "same_branch_resolution_without_true_stall",
            "required_entry_state": "partial_progress_on_same_branch",
            "required_source_bucket": SOURCE_BUCKET,
            "selected_branch": current_branch,
            "preferred_outcome": "one_shot_or_multi_step_same_branch_success",
        },
    }


def build_v0_3_12_bias_shift_task(task: dict) -> dict | None:
    if _norm(task.get("hidden_base_operator")).lower() != EXPANSION_OPERATOR:
        return None
    mutations = _mutation_rows(task)
    if len(mutations) < 2:
        return None
    first_name = _norm(mutations[0].get("param_name"))
    second_name = _norm(mutations[1].get("param_name"))
    if not first_name or not second_name or first_name == second_name:
        return None
    current_branch = f"continue_on_{first_name}"
    preferred_branch = f"switch_to_{second_name}"
    return {
        **task,
        "v0_3_12_family_id": FAMILY_ID,
        "source_primary_bucket": SOURCE_BUCKET,
        "sample_source_mode": "paired_value_bias_shift_expansion",
        "residual_hidden_parameters": [first_name, second_name],
        "current_branch": current_branch,
        "selected_branch": current_branch,
        "preferred_branch": preferred_branch,
        "candidate_branches": _build_branch_candidates(first_name, second_name),
        "candidate_next_branches": _build_branch_candidates(first_name, second_name),
        "baseline_measurement_protocol": _baseline_measurement_protocol(),
        "v0_3_12_one_shot_design": {
            "mainline_problem": "same_branch_resolution_without_true_stall",
            "required_entry_state": "post_restore_hidden_residual_exposed",
            "required_source_bucket": SOURCE_BUCKET,
            "selected_branch": current_branch,
            "preferred_outcome": "one_shot_or_multi_step_same_branch_success",
            "expansion_operator": EXPANSION_OPERATOR,
        },
    }


def build_v0_3_12_one_shot_taskset(
    *,
    legacy_taskset_path: str = DEFAULT_LEGACY_TASKSET,
    expansion_source_taskset_path: str = DEFAULT_EXPANSION_SOURCE_TASKSET,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    legacy_payload = _load_json(legacy_taskset_path)
    expansion_payload = _load_json(expansion_source_taskset_path)
    converted = []
    skipped_legacy = []
    skipped_expansion = []
    seen_task_ids: set[str] = set()

    for task in _task_rows(legacy_payload):
        converted_task = build_v0_3_12_legacy_task(task)
        if converted_task is None:
            skipped_legacy.append(_norm(task.get("task_id")))
            continue
        task_id = _norm(converted_task.get("task_id"))
        if task_id in seen_task_ids:
            continue
        seen_task_ids.add(task_id)
        converted.append(converted_task)

    for task in _task_rows(expansion_payload):
        converted_task = build_v0_3_12_bias_shift_task(task)
        if converted_task is None:
            skipped_expansion.append(_norm(task.get("task_id")))
            continue
        task_id = _norm(converted_task.get("task_id"))
        if task_id in seen_task_ids:
            skipped_expansion.append(task_id)
            continue
        seen_task_ids.add(task_id)
        converted.append(converted_task)

    out_root = Path(out_dir)
    for task in converted:
        _write_json(out_root / "tasks" / f"{task['task_id']}.json", task)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if converted else "EMPTY",
        "family_id": FAMILY_ID,
        "source_primary_bucket": SOURCE_BUCKET,
        "legacy_taskset_path": str(Path(legacy_taskset_path).resolve()) if Path(legacy_taskset_path).exists() else str(legacy_taskset_path),
        "expansion_source_taskset_path": (
            str(Path(expansion_source_taskset_path).resolve()) if Path(expansion_source_taskset_path).exists() else str(expansion_source_taskset_path)
        ),
        "task_count": len(converted),
        "task_ids": [str(task.get("task_id") or "") for task in converted],
        "skipped_legacy_task_ids": [row for row in skipped_legacy if row],
        "skipped_expansion_task_ids": [row for row in skipped_expansion if row],
        "baseline_measurement_protocol": _baseline_measurement_protocol(),
        "tasks": converted,
    }
    _write_json(out_root / "taskset.json", summary)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.12 One-Shot Taskset",
                "",
                f"- status: `{summary.get('status')}`",
                f"- family_id: `{summary.get('family_id')}`",
                f"- source_primary_bucket: `{summary.get('source_primary_bucket')}`",
                f"- task_count: `{summary.get('task_count')}`",
                "",
            ]
        ),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.12 one-shot candidate taskset.")
    parser.add_argument("--legacy-taskset", default=DEFAULT_LEGACY_TASKSET)
    parser.add_argument("--expansion-source-taskset", default=DEFAULT_EXPANSION_SOURCE_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_12_one_shot_taskset(
        legacy_taskset_path=str(args.legacy_taskset),
        expansion_source_taskset_path=str(args.expansion_source_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))


if __name__ == "__main__":
    main()
