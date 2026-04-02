from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_multi_round_validation_workorder_v0_3_4"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_multi_round_validation_workorder_v0_3_4"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def build_multi_round_validation_workorder(
    *,
    dev_priorities_summary_path: str,
    refreshed_candidate_taskset_path: str,
    max_tasks: int = 5,
) -> dict:
    priorities = _load_json(dev_priorities_summary_path)
    refreshed = _load_json(refreshed_candidate_taskset_path)
    best_lane = priorities.get("best_harder_lane") if isinstance(priorities.get("best_harder_lane"), dict) else {}
    family_id = str(best_lane.get("family_id") or "").strip()
    freeze_ready_ids = [str(x) for x in (best_lane.get("freeze_ready_ids") or []) if str(x or "").strip()]
    tasks = refreshed.get("tasks") if isinstance(refreshed.get("tasks"), list) else []
    rows: list[dict] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id") or "").strip()
        if task_id not in freeze_ready_ids:
            continue
        if str(task.get("v0_3_family_id") or "").strip() != family_id:
            continue
        rows.append(
            {
                "task_id": task_id,
                "failure_type": str(task.get("failure_type") or ""),
                "source_package_name": str(task.get("source_package_name") or ""),
                "source_qualified_model_name": str(task.get("source_qualified_model_name") or ""),
                "recommended_env": {
                    "GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR": "1",
                },
            }
        )
    selected_rows = rows[: max(0, int(max_tasks))]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "READY_FOR_LOCAL_VALIDATION" if selected_rows else "NO_TASKS_SELECTED",
        "inputs": {
            "dev_priorities_summary_path": str(Path(dev_priorities_summary_path).resolve()) if Path(dev_priorities_summary_path).exists() else str(dev_priorities_summary_path),
            "refreshed_candidate_taskset_path": str(Path(refreshed_candidate_taskset_path).resolve()) if Path(refreshed_candidate_taskset_path).exists() else str(refreshed_candidate_taskset_path),
        },
        "selected_family_id": family_id,
        "selected_task_count": len(selected_rows),
        "tasks": selected_rows,
        "command_template": (
            "env GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR=1 "
            "python3 -m gateforge.agent_modelica_live_executor_v1 "
            "--model-path <MODEL_PATH> --failure-type <FAILURE_TYPE> --source-model-path <SOURCE_MODEL_PATH> --source-qualified-model-name <MODEL_NAME>"
        ),
        "next_actions": [
            "Validate the selected multi-round cases locally with deterministic repair enabled before broadening the family-wide default.",
            "If at least two cases are rescued without planner or replay, promote multi-round deterministic repair validation as a v0.3.4 development lever.",
        ],
    }
    return payload


def _render_markdown(payload: dict) -> str:
    lines = [
        "# Multi-Round Validation Workorder v0.3.4",
        "",
        f"- status: `{payload.get('status')}`",
        f"- selected_family_id: `{payload.get('selected_family_id')}`",
        f"- selected_task_count: `{payload.get('selected_task_count')}`",
        "",
        "## Tasks",
        "",
    ]
    for row in payload.get("tasks") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- `{row.get('task_id')}` "
            f"(failure_type=`{row.get('failure_type')}`, model=`{row.get('source_qualified_model_name')}`)"
        )
    lines.extend(["", "## Next Actions", ""])
    for idx, action in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{idx}. {action}")
    lines.append("")
    return "\n".join(lines)


def run_multi_round_validation_workorder(
    *,
    dev_priorities_summary_path: str,
    refreshed_candidate_taskset_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
    max_tasks: int = 5,
) -> dict:
    payload = build_multi_round_validation_workorder(
        dev_priorities_summary_path=dev_priorities_summary_path,
        refreshed_candidate_taskset_path=refreshed_candidate_taskset_path,
        max_tasks=max_tasks,
    )
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", _render_markdown(payload))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a v0.3.4 multi-round deterministic validation workorder.")
    parser.add_argument("--dev-priorities-summary", required=True)
    parser.add_argument("--refreshed-candidate-taskset", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--max-tasks", type=int, default=5)
    args = parser.parse_args()
    payload = run_multi_round_validation_workorder(
        dev_priorities_summary_path=str(args.dev_priorities_summary),
        refreshed_candidate_taskset_path=str(args.refreshed_candidate_taskset),
        out_dir=str(args.out_dir),
        max_tasks=int(args.max_tasks),
    )
    print(json.dumps({"status": payload.get("status"), "selected_task_count": payload.get("selected_task_count")}))


if __name__ == "__main__":
    main()
