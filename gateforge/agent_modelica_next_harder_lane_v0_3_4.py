from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_track_c_primary_slice_v0_3_3 import (
    _attribution_gate,
    _family_gate,
    _planner_sensitivity_gate,
)


SCHEMA_VERSION = "agent_modelica_next_harder_lane_v0_3_4"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_next_harder_lane_v0_3_4"


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
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _lane_rows(payload: dict) -> list[dict]:
    rows = payload.get("lane_rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("item_id") or row.get("task_id") or row.get("mutation_id"))


def _select_family_id(lane_gate_summary: dict, requested_family_id: str) -> str:
    if _norm(requested_family_id):
        return _norm(requested_family_id)
    ready_rows = [row for row in _lane_rows(lane_gate_summary) if _norm(row.get("status")) == "FREEZE_READY"]
    if not ready_rows:
        return ""
    top = max(
        ready_rows,
        key=lambda row: (int(row.get("freeze_ready_count") or 0), _norm(row.get("family_id"))),
    )
    return _norm(top.get("family_id"))


def build_next_harder_lane(
    *,
    refreshed_candidate_taskset_path: str,
    lane_gate_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
    family_id: str = "",
) -> dict:
    refreshed = _load_json(refreshed_candidate_taskset_path)
    lane_gate = _load_json(lane_gate_summary_path)
    selected_family_id = _select_family_id(lane_gate, family_id)
    rows = _task_rows(refreshed)
    frozen_rows: list[dict] = []
    for row in rows:
        if _norm(row.get("v0_3_family_id")) != selected_family_id:
            continue
        if not bool(row.get("holdout_clean")):
            continue
        family_ok, _ = _family_gate(row)
        attribution_ok, _ = _attribution_gate(row)
        planner_ok, _ = _planner_sensitivity_gate(row)
        if family_ok and attribution_ok and planner_ok:
            frozen_rows.append({**row, "item_id": _item_id(row)})

    status = "PASS" if selected_family_id and frozen_rows else "FAIL"
    out_root = Path(out_dir)
    taskset_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "family_id": selected_family_id,
        "tasks": frozen_rows,
    }
    _write_json(out_root / "taskset_frozen.json", taskset_payload)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "selected_family_id": selected_family_id,
        "refreshed_candidate_taskset_path": str(Path(refreshed_candidate_taskset_path).resolve()) if Path(refreshed_candidate_taskset_path).exists() else str(refreshed_candidate_taskset_path),
        "lane_gate_summary_path": str(Path(lane_gate_summary_path).resolve()) if Path(lane_gate_summary_path).exists() else str(lane_gate_summary_path),
        "task_count": len(frozen_rows),
        "taskset_frozen_path": str((out_root / "taskset_frozen.json").resolve()),
        "task_ids": [_item_id(row) for row in frozen_rows],
    }
    _write_json(out_root / "summary.json", summary)
    _write_text(out_root / "summary.md", render_markdown(summary))
    return summary


def render_markdown(payload: dict) -> str:
    lines = [
        "# Agent Modelica Next Harder Lane v0.3.4",
        "",
        f"- status: `{payload.get('status')}`",
        f"- selected_family_id: `{payload.get('selected_family_id')}`",
        f"- task_count: `{payload.get('task_count')}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the next harder v0.3.4 lane from refreshed holdout-clean candidates.")
    parser.add_argument("--refreshed-candidate-taskset", required=True)
    parser.add_argument("--lane-gate-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--family-id", default="")
    args = parser.parse_args()
    payload = build_next_harder_lane(
        refreshed_candidate_taskset_path=str(args.refreshed_candidate_taskset),
        lane_gate_summary_path=str(args.lane_gate_summary),
        out_dir=str(args.out_dir),
        family_id=str(args.family_id),
    )
    print(json.dumps({"status": payload.get("status"), "selected_family_id": payload.get("selected_family_id"), "task_count": payload.get("task_count")}))


if __name__ == "__main__":
    main()
