from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_19_2_common import (
    DEFAULT_TRAJECTORY_OUT_DIR,
    DEFAULT_V191_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .stop_signal_v0_19_0 import HARD_CAP_TURNS
from .trajectory_schema_v0_19_0 import (
    SCHEMA_VERSION_SUMMARY,
    SCHEMA_VERSION_TURN,
    compute_progressive_solve,
    validate_summary_record,
    validate_turn_record,
)

DEFAULT_EXECUTOR_CMD = [sys.executable, "-m", "gateforge.agent_modelica_live_executor_v1"]
REQUIRED_BENCHMARK_CASE_FIELDS = (
    "candidate_id",
    "mutated_model_path",
    "source_model_path",
    "failure_type",
    "expected_stage",
)


def _missing_case_fields(case: dict) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_BENCHMARK_CASE_FIELDS:
        if not str(case.get(field) or "").strip():
            missing.append(field)
    return missing


def _path_exists(text: str) -> bool:
    value = str(text or "").strip()
    return bool(value) and Path(value).exists()


def _build_executor_cmd(case: dict, out_path: Path, executor_cmd: list[str]) -> list[str]:
    cmd = list(executor_cmd)
    task_id = str(case.get("task_id") or case.get("candidate_id") or "")
    cmd += [
        "--task-id", task_id,
        "--failure-type", str(case.get("failure_type") or ""),
        "--expected-stage", str(case.get("expected_stage") or ""),
        "--source-model-path", str(case.get("source_model_path") or ""),
        "--mutated-model-path", str(case.get("mutated_model_path") or ""),
        "--max-rounds", str(case.get("max_rounds") or HARD_CAP_TURNS),
        "--timeout-sec", str(case.get("timeout_sec") or 180),
        "--simulate-stop-time", str(case.get("simulate_stop_time") or 0.2),
        "--simulate-intervals", str(case.get("simulate_intervals") or 20),
        "--out", str(out_path),
    ]
    workflow_goal = str(case.get("workflow_goal") or "").strip()
    if workflow_goal:
        cmd += ["--workflow-goal", workflow_goal]
    backend = str(case.get("backend") or "").strip()
    if backend:
        cmd += ["--backend", backend]
    planner_backend = str(case.get("planner_backend") or "").strip()
    if planner_backend:
        cmd += ["--planner-backend", planner_backend]
    return cmd


def _derive_turn_outcomes(attempts: list[dict], executor_status: str) -> list[str]:
    outcomes: list[str] = []
    prior_failure = ""
    for idx, attempt in enumerate(attempts):
        observed = str(attempt.get("observed_failure_type") or "")
        is_last = idx == len(attempts) - 1
        if is_last and str(executor_status or "").upper() == "PASS":
            outcomes.append("success")
        elif prior_failure and observed and observed != prior_failure:
            outcomes.append("partial_progress")
        else:
            outcomes.append("no_progress")
        if observed:
            prior_failure = observed
    return outcomes


def _derive_termination_reason(attempts: list[dict], executor_status: str) -> str:
    if str(executor_status or "").upper() == "PASS":
        return "success"
    observed = [str(row.get("observed_failure_type") or "") for row in attempts if str(row.get("observed_failure_type") or "").strip()]
    if len(observed) >= 2 and observed[-1] == observed[-2]:
        return "stalled"
    if len(attempts) >= HARD_CAP_TURNS:
        return "timeout"
    return "cycling"


def _convert_executor_payload(case: dict, payload: dict) -> tuple[list[dict], dict]:
    attempts = list(payload.get("attempts") or [])
    if not attempts:
        raise ValueError(f"executor payload for {case.get('candidate_id')} has no attempts")
    task_id = str(payload.get("task_id") or case.get("candidate_id") or "")
    taxonomy_chain = [str(x) for x in (case.get("taxonomy_chain") or []) if str(x).strip()]
    executor_status = str(payload.get("executor_status") or "")
    turn_outcomes = _derive_turn_outcomes(attempts, executor_status)
    turn_records: list[dict] = []
    for idx, attempt in enumerate(attempts, start=1):
        observed = str(attempt.get("observed_failure_type") or payload.get("failure_type") or "")
        simulation_status = "PASS" if turn_outcomes[idx - 1] == "success" else "FAIL"
        record = {
            "schema_version": SCHEMA_VERSION_TURN,
            "task_id": task_id,
            "turn_id": idx,
            "prompt": {
                "system": "Captured live executor repair turn.",
                "user": f"Live benchmark repair for {task_id} with taxonomy chain {'/'.join(taxonomy_chain)}.",
            },
            "llm_response": {
                "raw": json.dumps(attempt, sort_keys=True),
                "parsed_patch": str(attempt.get("patched_model_text") or ""),
                "parsed_reasoning": str(attempt.get("reason") or attempt.get("llm_plan_failure_mode") or ""),
            },
            "execution": {
                "simulation_status": simulation_status,
                "error_message": str(attempt.get("compile_error") or attempt.get("simulate_error") or observed),
                "error_class": observed,
                "error_stage": str(attempt.get("diagnostic_ir", {}).get("stage") or payload.get("expected_stage") or ""),
            },
            "turn_outcome": turn_outcomes[idx - 1],
        }
        errors = validate_turn_record(record)
        if errors:
            raise ValueError(f"invalid turn record for {task_id}: {errors}")
        turn_records.append(record)
    final_outcome = "success" if str(executor_status).upper() == "PASS" else "failure"
    summary = {
        "schema_version": SCHEMA_VERSION_SUMMARY,
        "task_id": task_id,
        "total_turns": len(turn_records),
        "termination_reason": _derive_termination_reason(attempts, executor_status),
        "final_outcome": final_outcome,
        "progressive_solve": compute_progressive_solve(turn_outcomes, final_outcome),
        "turn_outcomes": turn_outcomes,
    }
    errors = validate_summary_record(summary)
    if errors:
        raise ValueError(f"invalid summary record for {task_id}: {errors}")
    return turn_records, summary


def build_v192_trajectory_runner(
    *,
    v191_closeout_path: str = str(DEFAULT_V191_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_TRAJECTORY_OUT_DIR),
    executor_cmd: list[str] | None = None,
) -> dict:
    closeout = load_json(v191_closeout_path)
    benchmark_rows = list((closeout.get("benchmark", {}) or {}).get("admitted_cases") or [])
    generator_rows = {
        str(row.get("candidate_id") or ""): row
        for row in (closeout.get("generator", {}) or {}).get("rows") or []
    }
    command = list(executor_cmd) if executor_cmd is not None else list(DEFAULT_EXECUTOR_CMD)
    out_root = Path(out_dir)
    raw_root = out_root / "raw_executor"
    raw_root.mkdir(parents=True, exist_ok=True)

    trajectories: list[dict] = []
    loop_summaries: list[dict] = []
    turn_records: list[dict] = []
    termination_counts: Counter[str] = Counter()
    infrastructure_failure_count = 0
    infrastructure_failures: list[dict] = []

    for case in benchmark_rows:
        candidate_id = str(case.get("candidate_id") or "")
        generator_row = generator_rows.get(candidate_id, {})
        if not generator_row:
            infrastructure_failure_count += 1
            infrastructure_failures.append(
                {
                    "candidate_id": candidate_id,
                    "missing_fields": ["generator_row"],
                    "missing_paths": [],
                }
            )
            continue
        missing = _missing_case_fields(case)
        missing_paths = [
            field for field in ("mutated_model_path", "source_model_path")
            if str(case.get(field) or "").strip() and not _path_exists(str(case.get(field) or ""))
        ]
        if missing or missing_paths:
            infrastructure_failure_count += 1
            infrastructure_failures.append(
                {
                    "candidate_id": candidate_id,
                    "missing_fields": missing,
                    "missing_paths": missing_paths,
                }
            )
            continue

        executor_out = raw_root / f"{candidate_id}.json"
        cmd = _build_executor_cmd(case, executor_out, command)
        timeout_sec = max(60, int(case.get("timeout_sec") or 180) + 30)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout_sec)
        except subprocess.TimeoutExpired as exc:
            infrastructure_failure_count += 1
            infrastructure_failures.append(
                {
                    "candidate_id": candidate_id,
                    "missing_fields": [],
                    "missing_paths": [],
                    "executor_returncode": None,
                    "stderr": str(exc.stderr or "")[-500:],
                    "stdout": str(exc.stdout or "")[-500:],
                    "timeout_sec": timeout_sec,
                }
            )
            continue
        if proc.returncode != 0 or not executor_out.exists():
            infrastructure_failure_count += 1
            infrastructure_failures.append(
                {
                    "candidate_id": candidate_id,
                    "missing_fields": [],
                    "missing_paths": [],
                    "executor_returncode": proc.returncode,
                    "stderr": proc.stderr[-500:],
                    "stdout": proc.stdout[-500:],
                }
            )
            continue
        executor_payload = load_json(executor_out)
        case_payload = dict(case)
        case_payload["taxonomy_chain"] = [
            str(generator_row.get("surface_layer_taxonomy_id") or ""),
            str(generator_row.get("residual_layer_taxonomy_id") or ""),
        ] + ([str(generator_row.get("optional_third_layer_taxonomy_id") or "")] if str(generator_row.get("optional_third_layer_taxonomy_id") or "").strip() else [])
        case_turns, case_summary = _convert_executor_payload(case_payload, executor_payload)
        trajectories.append(
            {
                "task_id": case_summary["task_id"],
                "candidate_id": candidate_id,
                "taxonomy_chain": [x for x in case_payload["taxonomy_chain"] if x],
                "turn_records": case_turns,
                "loop_summary": case_summary,
                "final_outcome": case_summary["final_outcome"],
                "termination_reason": case_summary["termination_reason"],
                "progressive_solve": case_summary["progressive_solve"],
                "executor_payload_path": str(executor_out),
            }
        )
        loop_summaries.append(case_summary)
        turn_records.extend(case_turns)
        termination_counts[case_summary["termination_reason"]] += 1

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_trajectory_runner",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "frontier_agent_id": str(closeout.get("conclusion", {}).get("frontier_agent_id") or ""),
        "target_max_turns": HARD_CAP_TURNS,
        "trajectory_case_count": len(trajectories),
        "turn_record_count": len(turn_records),
        "loop_summary_count": len(loop_summaries),
        "complete_case_count": len(loop_summaries),
        "infrastructure_failure_count": infrastructure_failure_count,
        "infrastructure_failures": infrastructure_failures,
        "max_turns_used": max((summary["total_turns"] for summary in loop_summaries), default=0),
        "termination_reason_counts": dict(sorted(termination_counts.items())),
        "trajectories": trajectories,
        "turn_records": turn_records,
        "loop_summaries": loop_summaries,
        "executor_cmd": [str(x) for x in command],
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.2 Trajectory Dataset",
                "",
                f"- trajectory_case_count: `{payload['trajectory_case_count']}`",
                f"- turn_record_count: `{payload['turn_record_count']}`",
                f"- complete_case_count: `{payload['complete_case_count']}`",
                f"- infrastructure_failure_count: `{infrastructure_failure_count}`",
                f"- executor_cmd: `{shlex.join(command)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.2 trajectory dataset artifact.")
    parser.add_argument("--v191-closeout", default=str(DEFAULT_V191_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_TRAJECTORY_OUT_DIR))
    parser.add_argument("--executor-cmd", default="")
    args = parser.parse_args()
    executor_cmd = shlex.split(str(args.executor_cmd)) if str(args.executor_cmd or "").strip() else None
    payload = build_v192_trajectory_runner(
        v191_closeout_path=str(args.v191_closeout),
        out_dir=str(args.out_dir),
        executor_cmd=executor_cmd,
    )
    print(json.dumps({"status": payload["status"], "complete_case_count": payload["complete_case_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
