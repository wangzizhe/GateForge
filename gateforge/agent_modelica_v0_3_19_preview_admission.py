from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_19_common import (
    DEFAULT_PREVIEW_OUT_DIR,
    DEFAULT_PREVIEW_RESULTS_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    error_signature_from_attempt,
    load_json,
    now_utc,
    norm,
    run_synthetic_task_live,
    second_snapshot,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_19_taskset import build_v0319_taskset


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_preview_admission"


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _detail_for_task(task: dict, *, results_dir: str, timeout_sec: int) -> dict:
    fixture = task.get("v0_3_19_fixture_one_step_detail")
    if isinstance(fixture, dict):
        return {
            "result_json_path": "",
            "detail": fixture,
            "return_code": 0,
            "planner_backend": "fixture",
            "max_rounds": 2,
        }
    return run_synthetic_task_live(
        task=task,
        result_dir=results_dir,
        evaluation_label="v0319_preview_admission",
        max_rounds=2,
        timeout_sec=timeout_sec,
    )


def _first_snapshot(detail: dict) -> dict:
    attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
    if attempts:
        first = attempts[0]
        diagnostic = first.get("diagnostic_ir") if isinstance(first.get("diagnostic_ir"), dict) else {}
        return {
            "dominant_stage_subtype": norm(diagnostic.get("dominant_stage_subtype") or detail.get("dominant_stage_subtype")),
            "error_subtype": norm(diagnostic.get("error_subtype")),
            "reason": norm(first.get("reason") or diagnostic.get("reason")),
            "error_signature": error_signature_from_attempt(first),
        }
    return {
        "dominant_stage_subtype": norm(detail.get("dominant_stage_subtype")),
        "error_subtype": "",
        "reason": "",
        "error_signature": "",
    }


def build_v0319_preview_admission(
    *,
    taskset_path: str = str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"),
    results_dir: str = str(DEFAULT_PREVIEW_RESULTS_DIR),
    out_dir: str = str(DEFAULT_PREVIEW_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    if not Path(taskset_path).exists():
        build_v0319_taskset(out_dir=str(Path(taskset_path).parent))
    taskset = load_json(taskset_path)
    tasks = _task_rows(taskset)
    rows: list[dict] = []
    admitted_tasks: list[dict] = []
    exposure_by_placement: dict[str, dict[str, int]] = {}
    for task in tasks:
        live = _detail_for_task(task, results_dir=results_dir, timeout_sec=timeout_sec)
        detail = live.get("detail") if isinstance(live.get("detail"), dict) else {}
        first = _first_snapshot(detail)
        attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
        second_attempt_observed = len(attempts) >= 2 and isinstance(attempts[1], dict)
        second = second_snapshot(detail) if second_attempt_observed or str(detail.get("executor_status") or "").upper() == "PASS" else {}
        second_signature = ""
        if second_attempt_observed:
            second_signature = error_signature_from_attempt(attempts[1])
        first_hit = (
            norm(first.get("dominant_stage_subtype")) == "stage_2_structural_balance_reference"
            and norm(first.get("error_subtype")) == "undefined_symbol"
        )
        second_residual_present = bool(second_attempt_observed and norm(second.get("residual_signal_cluster")) != "resolved")
        second_hit = (
            norm(second.get("dominant_stage_subtype")) == "stage_2_structural_balance_reference"
            and norm(second.get("error_subtype")) == "undefined_symbol"
        )
        signature_changed = bool(first.get("error_signature")) and bool(second_signature) and first.get("error_signature") != second_signature
        admitted = bool(first_hit and second_residual_present and second_hit)
        row = {
            "task_id": task.get("task_id"),
            "complexity_tier": task.get("complexity_tier"),
            "placement_kind": task.get("v0_3_19_placement_kind"),
            "mutation_shape": task.get("v0_3_19_mutation_shape"),
            "result_json_path": live.get("result_json_path"),
            "executor_status": detail.get("executor_status"),
            "rounds_used": detail.get("rounds_used"),
            "planner_event_count": ((detail.get("executor_runtime_hygiene") or {}).get("planner_event_count") if isinstance(detail.get("executor_runtime_hygiene"), dict) else None),
            "first_failure": first,
            "second_residual": second,
            "first_failure_hit": first_hit,
            "second_attempt_observed": second_attempt_observed,
            "second_residual_present": second_residual_present,
            "second_residual_hit": second_hit,
            "error_signature_changed": signature_changed,
            "admitted": admitted,
        }
        rows.append(row)
        if admitted:
            admitted_task = dict(task)
            admitted_task["v0_3_19_preview_row"] = row
            admitted_tasks.append(admitted_task)
        placement = norm(task.get("v0_3_19_placement_kind")) or "unknown"
        bucket = exposure_by_placement.setdefault(placement, {"total": 0, "second_residual_hit_count": 0, "signature_changed_count": 0})
        bucket["total"] += 1
        if second_hit:
            bucket["second_residual_hit_count"] += 1
        if signature_changed:
            bucket["signature_changed_count"] += 1
    placement_rates = {
        key: {
            **value,
            "second_residual_exposure_rate_pct": round(100.0 * value["second_residual_hit_count"] / float(value["total"]), 1) if value["total"] else 0.0,
            "signature_changed_rate_pct": round(100.0 * value["signature_changed_count"] / float(value["total"]), 1) if value["total"] else 0.0,
        }
        for key, value in exposure_by_placement.items()
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "taskset_path": str(Path(taskset_path).resolve()) if Path(taskset_path).exists() else str(taskset_path),
        "task_count": len(rows),
        "first_failure_hit_count": sum(1 for row in rows if bool(row.get("first_failure_hit"))),
        "second_residual_hit_count": sum(1 for row in rows if bool(row.get("second_residual_hit"))),
        "signature_changed_count": sum(1 for row in rows if bool(row.get("error_signature_changed"))),
        "admitted_task_count": len(admitted_tasks),
        "placement_rates": placement_rates,
        "rows": rows,
    }
    admitted_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if admitted_tasks else "EMPTY",
        "task_count": len(admitted_tasks),
        "task_ids": [norm(task.get("task_id")) for task in admitted_tasks],
        "tasks": admitted_tasks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "admitted_taskset.json", admitted_payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.19 Preview Admission",
                "",
                f"- status: `{summary.get('status')}`",
                f"- task_count: `{summary.get('task_count')}`",
                f"- admitted_task_count: `{summary.get('admitted_task_count')}`",
                f"- signature_changed_count: `{summary.get('signature_changed_count')}`",
                "",
            ]
        ),
    )
    return {"summary": summary, "admitted_taskset": admitted_payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.3.19 preview + live admission.")
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"))
    parser.add_argument("--results-dir", default=str(DEFAULT_PREVIEW_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_PREVIEW_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = build_v0319_preview_admission(
        taskset_path=str(args.taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "admitted_task_count": summary.get("admitted_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
