from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_19_common import (
    DEFAULT_LIVE_EVIDENCE_OUT_DIR,
    DEFAULT_LIVE_RESULTS_DIR,
    DEFAULT_PREVIEW_OUT_DIR,
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
from .agent_modelica_v0_3_19_preview_admission import build_v0319_preview_admission


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_live_evidence"


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _detail_for_task(task: dict, *, results_dir: str, timeout_sec: int) -> dict:
    fixture = task.get("v0_3_19_fixture_live_detail")
    if isinstance(fixture, dict):
        return {
            "result_json_path": "",
            "detail": fixture,
            "return_code": 0,
            "planner_backend": "fixture",
            "max_rounds": 4,
        }
    return run_synthetic_task_live(
        task=task,
        result_dir=results_dir,
        evaluation_label="v0319_live_evidence",
        max_rounds=4,
        timeout_sec=timeout_sec,
    )


def _chain_features(detail: dict) -> dict:
    attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
    first_signature = error_signature_from_attempt(attempts[0]) if len(attempts) >= 1 and isinstance(attempts[0], dict) else ""
    second_signature = error_signature_from_attempt(attempts[1]) if len(attempts) >= 2 and isinstance(attempts[1], dict) else ""
    first_diag = (attempts[0].get("diagnostic_ir") if len(attempts) >= 1 and isinstance(attempts[0], dict) and isinstance(attempts[0].get("diagnostic_ir"), dict) else {})
    second_diag = (attempts[1].get("diagnostic_ir") if len(attempts) >= 2 and isinstance(attempts[1], dict) and isinstance(attempts[1].get("diagnostic_ir"), dict) else {})
    first_hit = norm(first_diag.get("dominant_stage_subtype")) == "stage_2_structural_balance_reference" and norm(first_diag.get("error_subtype")) == "undefined_symbol"
    second_hit = norm(second_diag.get("dominant_stage_subtype")) == "stage_2_structural_balance_reference" and norm(second_diag.get("error_subtype")) == "undefined_symbol"
    return {
        "first_signature": first_signature,
        "second_signature": second_signature,
        "first_hit": first_hit,
        "second_hit": second_hit,
        "signature_changed": bool(first_signature) and bool(second_signature) and first_signature != second_signature,
    }


def build_v0319_live_evidence(
    *,
    admitted_taskset_path: str = str(DEFAULT_PREVIEW_OUT_DIR / "admitted_taskset.json"),
    results_dir: str = str(DEFAULT_LIVE_RESULTS_DIR),
    out_dir: str = str(DEFAULT_LIVE_EVIDENCE_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    if not Path(admitted_taskset_path).exists():
        build_v0319_preview_admission(out_dir=str(DEFAULT_PREVIEW_OUT_DIR))
    payload = load_json(admitted_taskset_path)
    tasks = _task_rows(payload)
    rows: list[dict] = []
    for task in tasks:
        live = _detail_for_task(task, results_dir=results_dir, timeout_sec=timeout_sec)
        detail = live.get("detail") if isinstance(live.get("detail"), dict) else {}
        second = second_snapshot(detail)
        chain = _chain_features(detail)
        planner_event_count = int(((detail.get("executor_runtime_hygiene") or {}).get("planner_event_count")) or 0) if isinstance(detail.get("executor_runtime_hygiene"), dict) else 0
        success = str(detail.get("executor_status") or "").upper() == "PASS"
        multiround_success = bool(success and chain["first_hit"] and chain["second_hit"] and chain["signature_changed"] and planner_event_count >= 1 and int(detail.get("rounds_used") or 0) >= 3)
        single_fix_success = bool(success and chain["first_hit"] and not chain["second_hit"])
        row = {
            "task_id": task.get("task_id"),
            "complexity_tier": task.get("complexity_tier"),
            "placement_kind": task.get("v0_3_19_placement_kind"),
            "result_json_path": live.get("result_json_path"),
            "executor_status": detail.get("executor_status"),
            "rounds_used": detail.get("rounds_used"),
            "planner_event_count": planner_event_count,
            "resolution_path": detail.get("resolution_path"),
            "second_residual": second,
            "first_error_signature": chain["first_signature"],
            "second_error_signature": chain["second_signature"],
            "error_signature_changed": chain["signature_changed"],
            "multiround_success": multiround_success,
            "single_fix_success": single_fix_success,
        }
        rows.append(row)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "admitted_taskset_path": str(Path(admitted_taskset_path).resolve()) if Path(admitted_taskset_path).exists() else str(admitted_taskset_path),
        "task_count": len(rows),
        "success_count": sum(1 for row in rows if norm(row.get("executor_status")).upper() == "PASS"),
        "multiround_success_count": sum(1 for row in rows if bool(row.get("multiround_success"))),
        "single_fix_success_count": sum(1 for row in rows if bool(row.get("single_fix_success"))),
        "signature_changed_count": sum(1 for row in rows if bool(row.get("error_signature_changed"))),
        "progressive_solve_rate_pct": round(100.0 * sum(1 for row in rows if bool(row.get("multiround_success"))) / float(len(rows)), 1) if rows else 0.0,
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.19 Live Evidence",
                "",
                f"- status: `{summary.get('status')}`",
                f"- task_count: `{summary.get('task_count')}`",
                f"- multiround_success_count: `{summary.get('multiround_success_count')}`",
                f"- single_fix_success_count: `{summary.get('single_fix_success_count')}`",
                "",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.3.19 live evidence on admitted tasks.")
    parser.add_argument("--admitted-taskset", default=str(DEFAULT_PREVIEW_OUT_DIR / "admitted_taskset.json"))
    parser.add_argument("--results-dir", default=str(DEFAULT_LIVE_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_LIVE_EVIDENCE_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = build_v0319_live_evidence(
        admitted_taskset_path=str(args.admitted_taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    print(json.dumps({"status": payload.get("status"), "multiround_success_count": payload.get("multiround_success_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
