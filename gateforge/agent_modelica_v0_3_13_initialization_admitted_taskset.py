from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_initialization_admitted_taskset"
DEFAULT_SOURCE_TASKSET = "artifacts/agent_modelica_v0_3_13_initialization_curriculum_taskset_current/taskset.json"
DEFAULT_PREVIEW_SUMMARY = "artifacts/agent_modelica_v0_3_13_initialization_curriculum_preview_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_initialization_admitted_taskset"
FAMILY_ID = "surface_cleanup_then_initialization_parameter_recovery"
COURSE_STAGE = "three_step_initialization_curriculum"


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


def _preview_map(payload: dict) -> dict[str, dict]:
    rows = payload.get("rows")
    mapping: dict[str, dict] = {}
    if not isinstance(rows, list):
        return mapping
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = _norm(row.get("task_id"))
        if task_id:
            mapping[task_id] = row
    return mapping


def build_initialization_admitted_row(*, source_task: dict, preview_row: dict) -> dict | None:
    if not bool(preview_row.get("preview_admission")):
        return None
    if _norm(preview_row.get("residual_signal_cluster_id")) != "initialization_parameter_recovery":
        return None
    return {
        **source_task,
        "v0_3_13_family_id": FAMILY_ID,
        "course_stage": COURSE_STAGE,
        "preview_contract": {
            "surface_fixable_by_rule": bool(preview_row.get("surface_fixable_by_rule")),
            "surface_rule_id": _norm(preview_row.get("surface_rule_id")),
            "post_rule_residual_stage": _norm(preview_row.get("post_rule_residual_stage")),
            "post_rule_residual_error_type": _norm(preview_row.get("post_rule_residual_error_type")),
            "post_rule_residual_reason": _norm(preview_row.get("post_rule_residual_reason")),
            "residual_signal_cluster_id": _norm(preview_row.get("residual_signal_cluster_id")),
            "preview_admission": bool(preview_row.get("preview_admission")),
        },
    }


def build_initialization_admitted_taskset(
    *,
    source_taskset_path: str = DEFAULT_SOURCE_TASKSET,
    preview_summary_path: str = DEFAULT_PREVIEW_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    source_taskset = _load_json(source_taskset_path)
    preview_summary = _load_json(preview_summary_path)
    preview_rows = _preview_map(preview_summary)
    tasks = []
    skipped = []
    out_root = Path(out_dir)
    for task in _task_rows(source_taskset):
        task_id = _norm(task.get("task_id"))
        converted = build_initialization_admitted_row(
            source_task=task,
            preview_row=preview_rows.get(task_id, {}),
        )
        if converted is None:
            skipped.append(task_id)
            continue
        tasks.append(converted)
        _write_json(out_root / "tasks" / f"{task_id}.json", converted)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if tasks else "EMPTY",
        "family_id": FAMILY_ID,
        "course_stage": COURSE_STAGE,
        "task_count": len(tasks),
        "task_ids": [row["task_id"] for row in tasks],
        "skipped_task_ids": skipped,
        "tasks": tasks,
    }
    _write_json(out_root / "taskset.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.13 Initialization Admitted Taskset",
                "",
                f"- status: `{payload.get('status')}`",
                f"- task_count: `{payload.get('task_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 initialization admitted taskset.")
    parser.add_argument("--source-taskset", default=DEFAULT_SOURCE_TASKSET)
    parser.add_argument("--preview-summary", default=DEFAULT_PREVIEW_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_initialization_admitted_taskset(
        source_taskset_path=str(args.source_taskset),
        preview_summary_path=str(args.preview_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
