from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_v0_3_13_residual_signal_whitelist import (
    DEFAULT_OUT_DIR as DEFAULT_WHITELIST_OUT_DIR,
    build_residual_signal_whitelist,
)
from .agent_modelica_v0_3_13_trajectory_preview import build_preview_row


SCHEMA_VERSION = "agent_modelica_v0_3_15_candidate_preview"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_candidate_lane_current" / "taskset.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_candidate_preview_current"


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


def build_candidate_preview(
    *,
    candidate_taskset_path: str = str(DEFAULT_CANDIDATE_TASKSET),
    whitelist_out_dir: str = DEFAULT_WHITELIST_OUT_DIR,
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    whitelist = build_residual_signal_whitelist(out_dir=whitelist_out_dir)
    candidate_payload = _load_json(candidate_taskset_path)
    tasks = _task_rows(candidate_payload)
    rows = []
    admitted_tasks = []
    reason_counts: dict[str, int] = {}
    for task in tasks:
        preview_row = task.get("v0_3_15_fixture_preview") if isinstance(task.get("v0_3_15_fixture_preview"), dict) else None
        if not isinstance(preview_row, dict):
            preview_row = build_preview_row(
                task=task,
                whitelist_payload=whitelist,
            )
        combined = dict(task)
        combined["preview"] = preview_row
        combined["v0_3_15_preview_admitted"] = bool(preview_row.get("preview_admission"))
        combined["v0_3_15_admitted_for_baseline"] = bool(task.get("v0_3_15_offline_exact_match_ready"))
        rows.append(combined)
        reason = _norm(preview_row.get("preview_reason")) or "unknown"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if combined["v0_3_15_admitted_for_baseline"]:
            admitted_tasks.append(task)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "candidate_taskset_path": str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path),
        "total_task_count": len(rows),
        "preview_admitted_count": sum(1 for row in rows if bool(row.get("v0_3_15_preview_admitted"))),
        "offline_exact_match_ready_count": sum(1 for row in rows if bool(row.get("v0_3_15_offline_exact_match_ready"))),
        "admitted_for_baseline_count": len(admitted_tasks),
        "preview_reason_counts": reason_counts,
        "rows": rows,
    }
    admitted_taskset = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if admitted_tasks else "EMPTY",
        "task_count": len(admitted_tasks),
        "task_ids": [row["task_id"] for row in admitted_tasks],
        "tasks": admitted_tasks,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", summary)
    _write_json(out_root / "admitted_taskset.json", admitted_taskset)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.15 Candidate Preview",
                "",
                f"- status: `{summary.get('status')}`",
                f"- total_task_count: `{summary.get('total_task_count')}`",
                f"- admitted_for_baseline_count: `{summary.get('admitted_for_baseline_count')}`",
                "",
            ]
        ),
    )
    return {
        "summary": summary,
        "admitted_taskset_path": str((out_root / "admitted_taskset.json").resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.3.15 preview admission on replay-sensitive candidates.")
    parser.add_argument("--candidate-taskset", default=str(DEFAULT_CANDIDATE_TASKSET))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_candidate_preview(
        candidate_taskset_path=str(args.candidate_taskset),
        out_dir=str(args.out_dir),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "admitted_for_baseline_count": summary.get("admitted_for_baseline_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
