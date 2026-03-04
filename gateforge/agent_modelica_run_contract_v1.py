from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Run Contract v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- success_count: `{payload.get('success_count')}`",
        f"- success_at_k_pct: `{payload.get('success_at_k_pct')}`",
        f"- median_time_to_pass_sec: `{payload.get('median_time_to_pass_sec')}`",
        f"- median_repair_rounds: `{payload.get('median_repair_rounds')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _run_task_mock(task: dict, max_rounds: int, max_time_sec: int) -> dict:
    success_round = int(task.get("mock_success_round", 2) or 2)
    round_sec = int(task.get("mock_round_duration_sec", 30) or 30)
    forced_regression_fail = bool(task.get("mock_force_regression_fail", False))
    forced_physics_fail = bool(task.get("mock_force_physics_fail", False))

    attempts: list[dict] = []
    total_time = 0
    passed = False
    rounds_used = 0
    hard = {
        "check_model_pass": False,
        "simulate_pass": False,
        "physics_contract_pass": False,
        "regression_pass": False,
    }

    for idx in range(1, max_rounds + 1):
        total_time += round_sec
        rounds_used = idx
        hit = idx >= success_round
        check_ok = hit
        simulate_ok = hit
        physics_ok = hit and not forced_physics_fail
        regression_ok = hit and not forced_regression_fail
        attempts.append(
            {
                "round": idx,
                "time_budget_exceeded": total_time > max_time_sec,
                "check_model_pass": check_ok,
                "simulate_pass": simulate_ok,
                "physics_contract_pass": physics_ok,
                "regression_pass": regression_ok,
            }
        )
        if check_ok and simulate_ok and physics_ok and regression_ok and total_time <= max_time_sec:
            passed = True
            hard = {
                "check_model_pass": True,
                "simulate_pass": True,
                "physics_contract_pass": True,
                "regression_pass": True,
            }
            break
        hard = {
            "check_model_pass": check_ok,
            "simulate_pass": simulate_ok,
            "physics_contract_pass": physics_ok,
            "regression_pass": regression_ok,
        }

    return {
        "task_id": str(task.get("task_id") or ""),
        "scale": str(task.get("scale") or "unknown"),
        "failure_type": str(task.get("failure_type") or "unknown"),
        "passed": passed,
        "rounds_used": rounds_used,
        "time_to_pass_sec": total_time if passed else None,
        "elapsed_sec": total_time,
        "hard_checks": hard,
        "attempts": attempts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute agent modelica run contract with bounded rounds/time")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--mode", choices=["mock"], default="mock")
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--max-time-sec", type=int, default=300)
    parser.add_argument("--results-out", default="artifacts/agent_modelica_run_contract_v1/results.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_run_contract_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    payload = _load_json(args.taskset)
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]
    reasons: list[str] = []
    if not tasks:
        reasons.append("taskset_empty")

    max_rounds = max(1, int(args.max_rounds))
    max_time_sec = max(1, int(args.max_time_sec))

    records: list[dict] = []
    for task in tasks:
        records.append(_run_task_mock(task, max_rounds=max_rounds, max_time_sec=max_time_sec))

    success_rows = [x for x in records if bool(x.get("passed"))]
    success_count = len(success_rows)
    times = [int(x.get("time_to_pass_sec")) for x in success_rows if isinstance(x.get("time_to_pass_sec"), int)]
    rounds = [int(x.get("rounds_used")) for x in success_rows if isinstance(x.get("rounds_used"), int)]
    regression_count = len([x for x in records if not bool((x.get("hard_checks") or {}).get("regression_pass"))])
    physics_fail_count = len([x for x in records if not bool((x.get("hard_checks") or {}).get("physics_contract_pass"))])

    median_time = round(statistics.median(times), 2) if times else None
    median_rounds = round(statistics.median(rounds), 2) if rounds else None
    status = "PASS"
    if reasons:
        status = "FAIL"
    elif success_count < len(records):
        status = "NEEDS_REVIEW"

    results_payload = {
        "schema_version": "agent_modelica_run_results_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": records,
    }
    _write_json(args.results_out, results_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": len(records),
        "success_count": success_count,
        "success_at_k_pct": _ratio(success_count, len(records)),
        "median_time_to_pass_sec": median_time,
        "median_repair_rounds": median_rounds,
        "regression_count": regression_count,
        "physics_fail_count": physics_fail_count,
        "max_rounds": max_rounds,
        "max_time_sec": max_time_sec,
        "results_out": args.results_out,
        "reasons": reasons,
        "sources": {"taskset": args.taskset},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "success_count": success_count, "total_tasks": len(records)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

