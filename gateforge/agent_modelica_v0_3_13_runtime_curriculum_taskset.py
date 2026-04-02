from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_runtime_curriculum_taskset"
DEFAULT_SOURCE_TASKSET = "artifacts/agent_modelica_post_restore_taskset_v0_3_6_current/taskset.json"
DEFAULT_PREVIEW_SUMMARY = "artifacts/agent_modelica_v0_3_13_trajectory_preview_v0_3_6_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_runtime_curriculum_taskset"
FAMILY_ID = "surface_cleanup_then_multi_parameter_runtime_recovery"
COURSE_STAGE = "three_step_runtime_curriculum"
REQUIRED_HIDDEN_BASE_OPERATOR = "paired_value_collapse"
REQUIRED_SIGNAL_CLUSTER = "runtime_parameter_recovery"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _preview_rows(payload: dict) -> dict[str, dict]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    mapping: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = _norm(row.get("task_id"))
        if task_id:
            mapping[task_id] = row
    return mapping


def _mutation_rows(task: dict) -> list[dict]:
    hidden = (task.get("mutation_spec") or {}).get("hidden_base")
    audit = hidden.get("audit") if isinstance(hidden, dict) else None
    rows = audit.get("mutations") if isinstance(audit, dict) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _family_design_contract() -> dict:
    return {
        "family_goal": "surface_cleanup_then_multi_parameter_runtime_recovery",
        "round_1_expectation": "deterministic cleanup removes the synthetic surface marker",
        "round_2_expectation": "multi-parameter runtime residual remains active after cleanup",
        "round_3_expectation": "the agent must choose a viable parameter recovery direction beyond a trivial one-shot cleanup",
    }


def build_runtime_curriculum_row(*, source_task: dict, preview_row: dict) -> dict | None:
    if _norm(source_task.get("hidden_base_operator")).lower() != REQUIRED_HIDDEN_BASE_OPERATOR:
        return None
    if not bool(preview_row.get("preview_admission")):
        return None
    if _norm(preview_row.get("residual_signal_cluster_id")) != REQUIRED_SIGNAL_CLUSTER:
        return None
    mutation_rows = _mutation_rows(source_task)
    parameter_names = [_norm(row.get("param_name")) for row in mutation_rows if _norm(row.get("param_name"))]
    return {
        **source_task,
        "v0_3_13_family_id": FAMILY_ID,
        "course_stage": COURSE_STAGE,
        "curriculum_source": "v0_3_6_post_restore_preview",
        "runtime_recovery_parameter_names": parameter_names,
        "preview_contract": {
            "surface_fixable_by_rule": bool(preview_row.get("surface_fixable_by_rule")),
            "surface_rule_id": _norm(preview_row.get("surface_rule_id")),
            "post_rule_residual_stage": _norm(preview_row.get("post_rule_residual_stage")),
            "post_rule_residual_error_type": _norm(preview_row.get("post_rule_residual_error_type")),
            "post_rule_residual_reason": _norm(preview_row.get("post_rule_residual_reason")),
            "residual_signal_cluster_id": _norm(preview_row.get("residual_signal_cluster_id")),
            "preview_admission": bool(preview_row.get("preview_admission")),
        },
        "design_contract": _family_design_contract(),
    }


def build_runtime_curriculum_taskset(
    *,
    source_taskset_path: str = DEFAULT_SOURCE_TASKSET,
    preview_summary_path: str = DEFAULT_PREVIEW_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    source_payload = _load_json(source_taskset_path)
    preview_payload = _load_json(preview_summary_path)
    preview_rows = _preview_rows(preview_payload)
    converted = []
    skipped_task_ids = []
    for task in _task_rows(source_payload):
        task_id = _norm(task.get("task_id"))
        converted_row = build_runtime_curriculum_row(
            source_task=task,
            preview_row=preview_rows.get(task_id, {}),
        )
        if converted_row is None:
            if task_id:
                skipped_task_ids.append(task_id)
            continue
        converted.append(converted_row)

    out_root = Path(out_dir)
    for row in converted:
        _write_json(out_root / "tasks" / f"{row['task_id']}.json", row)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if converted else "EMPTY",
        "family_id": FAMILY_ID,
        "course_stage": COURSE_STAGE,
        "source_taskset_path": str(Path(source_taskset_path).resolve()) if Path(source_taskset_path).exists() else str(source_taskset_path),
        "preview_summary_path": str(Path(preview_summary_path).resolve()) if Path(preview_summary_path).exists() else str(preview_summary_path),
        "required_hidden_base_operator": REQUIRED_HIDDEN_BASE_OPERATOR,
        "required_signal_cluster": REQUIRED_SIGNAL_CLUSTER,
        "task_count": len(converted),
        "task_ids": [row["task_id"] for row in converted],
        "skipped_task_ids": skipped_task_ids,
        "tasks": converted,
    }
    _write_json(out_root / "taskset.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.13 Runtime Curriculum Taskset",
                "",
                f"- status: `{payload.get('status')}`",
                f"- family_id: `{payload.get('family_id')}`",
                f"- task_count: `{payload.get('task_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 runtime curriculum taskset from the v0.3.6 source.")
    parser.add_argument("--source-taskset", default=DEFAULT_SOURCE_TASKSET)
    parser.add_argument("--preview-summary", default=DEFAULT_PREVIEW_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_runtime_curriculum_taskset(
        source_taskset_path=str(args.source_taskset),
        preview_summary_path=str(args.preview_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
