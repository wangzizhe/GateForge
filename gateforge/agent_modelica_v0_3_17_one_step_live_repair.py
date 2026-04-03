from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_17_common import (
    REPO_ROOT,
    classify_actionability,
    extract_snapshot,
    failure_type_for_second_run,
    first_repair_action_type,
    load_json,
    now_utc,
    run_generated_model_live,
    write_json,
    write_text,
)


SCHEMA_VERSION = "agent_modelica_v0_3_17_one_step_live_repair"
DEFAULT_REPAIR_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_generation_census_current" / "repair_taskset.json"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_one_step_live_results_current"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_17_one_step_live_repair_current"


def _second_snapshot(detail: dict, first_snapshot: dict) -> dict:
    attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
    if len(attempts) >= 2 and isinstance(attempts[1], dict):
        return extract_snapshot(detail, attempt_index=1)
    if str(detail.get("executor_status") or "").upper() == "PASS":
        return {
            "round_idx": 2,
            "dominant_stage_subtype": "stage_0_none",
            "error_subtype": "none",
            "observed_failure_type": "none",
            "reason": "",
            "residual_signal_cluster": "resolved",
            "declared_failure_type_canonical": first_snapshot.get("declared_failure_type_canonical"),
            "expected_stage": first_snapshot.get("expected_stage"),
            "suggested_actions": [],
        }
    carried = dict(first_snapshot)
    carried["round_idx"] = 2
    carried["residual_signal_cluster"] = str(first_snapshot.get("residual_signal_cluster") or "unknown_residual_signal")
    return carried


def _stage_distribution(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        snapshot = row.get("second_residual") if isinstance(row.get("second_residual"), dict) else {}
        stage = str(snapshot.get("dominant_stage_subtype") or "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def build_one_step_live_repair(
    *,
    repair_taskset_path: str = str(DEFAULT_REPAIR_TASKSET),
    results_dir: str = str(DEFAULT_RESULTS_DIR),
    out_dir: str = str(DEFAULT_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    taskset = load_json(repair_taskset_path)
    tasks = [row for row in (taskset.get("tasks") or []) if isinstance(row, dict)]
    rows: list[dict] = []
    for task in tasks:
        first_failure = task.get("first_failure") if isinstance(task.get("first_failure"), dict) else {}
        failure_type, expected_stage = failure_type_for_second_run(first_failure)
        live = run_generated_model_live(
            task_id=str(task.get("task_id") or ""),
            modelica_code=str(task.get("mutated_model_text") or task.get("source_model_text") or ""),
            result_dir=results_dir,
            evaluation_label="v0317_one_step_live_repair",
            max_rounds=2,
            declared_failure_type=failure_type,
            expected_stage=expected_stage,
            timeout_sec=timeout_sec,
        )
        detail = live.get("detail") if isinstance(live.get("detail"), dict) else {}
        second = _second_snapshot(detail, first_failure)
        row = {
            "task_id": task.get("task_id"),
            "complexity_tier": task.get("complexity_tier"),
            "result_json_path": live.get("result_json_path"),
            "executor_status": detail.get("executor_status"),
            "rounds_used": detail.get("rounds_used"),
            "resolution_path": detail.get("resolution_path"),
            "planner_invoked": detail.get("planner_invoked"),
            "planner_used": detail.get("planner_used"),
            "first_failure": first_failure,
            "repair_action_type": first_repair_action_type(detail),
            "second_residual": second,
            "second_residual_in_synthetic_keyspace": False,
            "immediate_pass_after_first_live_repair": second.get("residual_signal_cluster") == "resolved",
            "terminal_death_after_first_live_repair": str(detail.get("executor_status") or "").upper() != "PASS"
            and second.get("dominant_stage_subtype") not in {"stage_0_none", ""},
            "second_residual_actionability": classify_actionability(second),
        }
        rows.append(row)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "repair_taskset_path": str(Path(repair_taskset_path).resolve()) if Path(repair_taskset_path).exists() else str(repair_taskset_path),
        "task_count": len(rows),
        "immediate_pass_count": len([row for row in rows if bool(row.get("immediate_pass_after_first_live_repair"))]),
        "terminal_death_count": len([row for row in rows if bool(row.get("terminal_death_after_first_live_repair"))]),
        "second_residual_stage_distribution": _stage_distribution(rows),
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.17 One-Step Live Repair",
                "",
                f"- status: `{summary.get('status')}`",
                f"- task_count: `{summary.get('task_count')}`",
                f"- immediate_pass_count: `{summary.get('immediate_pass_count')}`",
                f"- terminal_death_count: `{summary.get('terminal_death_count')}`",
                "",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.17 one-step live repair census.")
    parser.add_argument("--repair-taskset", default=str(DEFAULT_REPAIR_TASKSET))
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = build_one_step_live_repair(
        repair_taskset_path=str(args.repair_taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
