from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .physics_contract_v0 import (
    DEFAULT_PHYSICS_CONTRACT_PATH,
    evaluate_physics_contract_v0,
    load_physics_contract_v0,
)
from .agent_modelica_repair_playbook_v1 import load_repair_playbook, recommend_repair_strategy
from .regression import compare_evidence, load_json as _load_evidence_json


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


def _default_baseline_metrics() -> dict:
    return {
        "steady_state_error": 0.01,
        "overshoot": 0.05,
        "settling_time": 1.0,
        "runtime_seconds": 1.0,
        "events": 10,
    }


def _default_candidate_metrics(failure_type: str, baseline_metrics: dict) -> dict:
    candidate = dict(baseline_metrics)
    if failure_type == "semantic_regression":
        candidate["steady_state_error"] = 0.03
    elif failure_type == "simulate_error":
        candidate["events"] = 8
    elif failure_type == "model_check_error":
        candidate["runtime_seconds"] = 1.2
    return candidate


def _run_task_mock(task: dict, max_rounds: int, max_time_sec: int, physics_contract: dict, repair_playbook: dict) -> dict:
    success_round = int(task.get("mock_success_round", 2) or 2)
    round_sec = int(task.get("mock_round_duration_sec", 30) or 30)
    forced_regression_fail = bool(task.get("mock_force_regression_fail", False))
    forced_physics_fail = bool(task.get("mock_force_physics_fail", False))
    failure_type = str(task.get("failure_type") or "unknown")
    task_invariants = task.get("physical_invariants") if isinstance(task.get("physical_invariants"), list) else []
    provided_baseline_metrics = task.get("baseline_metrics") if isinstance(task.get("baseline_metrics"), dict) else None
    baseline_metrics = dict(provided_baseline_metrics) if provided_baseline_metrics is not None else _default_baseline_metrics()
    provided_candidate_metrics = task.get("candidate_metrics") if isinstance(task.get("candidate_metrics"), dict) else None
    if provided_candidate_metrics is not None:
        candidate_metrics = dict(provided_candidate_metrics)
    elif provided_baseline_metrics is not None:
        candidate_metrics = dict(baseline_metrics)
    else:
        candidate_metrics = _default_candidate_metrics(failure_type=failure_type, baseline_metrics=baseline_metrics)

    attempts: list[dict] = []
    total_time = 0
    passed = False
    rounds_used = 0
    repair_strategy = recommend_repair_strategy(
        playbook_payload=repair_playbook,
        failure_type=failure_type,
        expected_stage=str(task.get("expected_stage") or "unknown"),
    )
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
        if not hit:
            physics_eval = {
                "pass": False,
                "reasons": ["physics_contract_not_evaluated_before_check_and_simulate_pass"],
                "findings": [],
                "invariant_count": 0,
            }
            physics_ok = False
        elif forced_physics_fail:
            physics_eval = {
                "pass": False,
                "reasons": ["physics_contract_forced_fail"],
                "findings": [],
                "invariant_count": len(task_invariants),
            }
            physics_ok = False
        else:
            try:
                physics_eval = evaluate_physics_contract_v0(
                    contract=physics_contract,
                    task_invariants=task_invariants,
                    baseline_metrics=baseline_metrics,
                    candidate_metrics=candidate_metrics,
                    scale=str(task.get("scale") or "unknown"),
                )
            except Exception as exc:
                physics_eval = {
                    "pass": False,
                    "reasons": [f"physics_contract_eval_error:{exc}"],
                    "findings": [],
                    "invariant_count": len(task_invariants),
                }
            physics_ok = bool(physics_eval.get("pass"))
        regression_ok = hit and not forced_regression_fail
        attempts.append(
            {
                "round": idx,
                "time_budget_exceeded": total_time > max_time_sec,
                "check_model_pass": check_ok,
                "simulate_pass": simulate_ok,
                "physics_contract_pass": physics_ok,
                "physics_contract_reasons": list(physics_eval.get("reasons") or []),
                "physics_contract_invariant_count": int(physics_eval.get("invariant_count") or 0),
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
        "failure_type": failure_type,
        "passed": passed,
        "rounds_used": rounds_used,
        "time_to_pass_sec": total_time if passed else None,
        "elapsed_sec": total_time,
        "hard_checks": hard,
        "repair_strategy": repair_strategy,
        "physics_contract_reasons": [
            str(x)
            for x in (attempts[-1].get("physics_contract_reasons") if attempts else [])
            if isinstance(x, str)
        ],
        "attempts": attempts,
    }


def _read_evidence_task(task: dict, key_inline: str, key_path: str) -> dict:
    inline = task.get(key_inline)
    if isinstance(inline, dict):
        return inline
    path = task.get(key_path)
    if isinstance(path, str) and path.strip():
        return _load_evidence_json(path.strip())
    return {}


def _run_task_evidence(
    task: dict,
    max_rounds: int,
    max_time_sec: int,
    physics_contract: dict,
    runtime_threshold: float,
    repair_playbook: dict,
) -> dict:
    scale = str(task.get("scale") or "unknown")
    failure_type = str(task.get("failure_type") or "unknown")
    repair_strategy = recommend_repair_strategy(
        playbook_payload=repair_playbook,
        failure_type=failure_type,
        expected_stage=str(task.get("expected_stage") or "unknown"),
    )
    rounds_used = max(1, int(task.get("observed_repair_rounds", 1) or 1))
    rounds_used = min(rounds_used, max_rounds)

    baseline_evidence = _read_evidence_task(task, "baseline_evidence", "baseline_evidence_path")
    candidate_evidence = _read_evidence_task(task, "candidate_evidence", "candidate_evidence_path")
    task_invariants = task.get("physical_invariants") if isinstance(task.get("physical_invariants"), list) else []

    base_metrics = baseline_evidence.get("metrics") if isinstance(baseline_evidence.get("metrics"), dict) else {}
    cand_metrics = candidate_evidence.get("metrics") if isinstance(candidate_evidence.get("metrics"), dict) else {}
    elapsed_sec = int(task.get("observed_elapsed_sec") or round(float(cand_metrics.get("runtime_seconds") or 0.0)))
    elapsed_sec = max(1, elapsed_sec)

    try:
        physics_eval = evaluate_physics_contract_v0(
            contract=physics_contract,
            task_invariants=task_invariants,
            baseline_metrics=base_metrics,
            candidate_metrics=cand_metrics,
            scale=scale,
        )
    except Exception as exc:
        physics_eval = {
            "pass": False,
            "reasons": [f"physics_contract_eval_error:{exc}"],
            "findings": [],
            "invariant_count": len(task_invariants),
        }

    try:
        regression = compare_evidence(
            baseline=baseline_evidence,
            candidate=candidate_evidence,
            runtime_regression_threshold=runtime_threshold,
            strict=False,
            checker_names=None,
            checker_config=task.get("checker_config") if isinstance(task.get("checker_config"), dict) else None,
        )
    except Exception as exc:
        regression = {
            "decision": "FAIL",
            "reasons": [f"regression_eval_error:{exc}"],
        }

    check_ok = bool(candidate_evidence.get("check_ok"))
    simulate_ok = bool(candidate_evidence.get("simulate_ok"))
    physics_ok = bool(physics_eval.get("pass"))
    regression_ok = str(regression.get("decision") or "FAIL") == "PASS"
    time_budget_exceeded = elapsed_sec > max_time_sec
    attempts = [
        {
            "round": rounds_used,
            "time_budget_exceeded": time_budget_exceeded,
            "check_model_pass": check_ok,
            "simulate_pass": simulate_ok,
            "physics_contract_pass": physics_ok,
            "physics_contract_reasons": list(physics_eval.get("reasons") or []),
            "physics_contract_invariant_count": int(physics_eval.get("invariant_count") or 0),
            "regression_pass": regression_ok,
            "regression_reasons": [str(x) for x in (regression.get("reasons") or []) if isinstance(x, str)],
        }
    ]
    passed = check_ok and simulate_ok and physics_ok and regression_ok and not time_budget_exceeded

    return {
        "task_id": str(task.get("task_id") or ""),
        "scale": scale,
        "failure_type": failure_type,
        "passed": passed,
        "rounds_used": rounds_used,
        "time_to_pass_sec": elapsed_sec if passed else None,
        "elapsed_sec": elapsed_sec,
        "hard_checks": {
            "check_model_pass": check_ok,
            "simulate_pass": simulate_ok,
            "physics_contract_pass": physics_ok,
            "regression_pass": regression_ok,
        },
        "repair_strategy": repair_strategy,
        "physics_contract_reasons": [str(x) for x in (physics_eval.get("reasons") or []) if isinstance(x, str)],
        "regression_reasons": [str(x) for x in (regression.get("reasons") or []) if isinstance(x, str)],
        "attempts": attempts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute agent modelica run contract with bounded rounds/time")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--mode", choices=["mock", "evidence"], default="mock")
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--max-time-sec", type=int, default=300)
    parser.add_argument("--runtime-threshold", type=float, default=0.2)
    parser.add_argument("--physics-contract", default=DEFAULT_PHYSICS_CONTRACT_PATH)
    parser.add_argument("--repair-playbook", default=None)
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
    physics_contract, physics_contract_source = load_physics_contract_v0(args.physics_contract)
    repair_playbook = load_repair_playbook(args.repair_playbook)

    records: list[dict] = []
    for task in tasks:
        if args.mode == "evidence":
            records.append(
                _run_task_evidence(
                    task,
                    max_rounds=max_rounds,
                    max_time_sec=max_time_sec,
                    physics_contract=physics_contract,
                    runtime_threshold=float(args.runtime_threshold),
                    repair_playbook=repair_playbook,
                )
            )
        else:
            records.append(
                _run_task_mock(
                    task,
                    max_rounds=max_rounds,
                    max_time_sec=max_time_sec,
                    physics_contract=physics_contract,
                    repair_playbook=repair_playbook,
                )
            )

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
        "physics_contract_schema_version": physics_contract.get("schema_version"),
        "physics_contract_source": physics_contract_source,
        "repair_playbook_source": repair_playbook.get("source") if isinstance(repair_playbook, dict) else None,
        "mode": args.mode,
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
        "physics_contract_schema_version": physics_contract.get("schema_version"),
        "physics_contract_source": physics_contract_source,
        "repair_playbook_source": repair_playbook.get("source") if isinstance(repair_playbook, dict) else None,
        "mode": args.mode,
        "max_rounds": max_rounds,
        "max_time_sec": max_time_sec,
        "runtime_threshold": float(args.runtime_threshold),
        "results_out": args.results_out,
        "reasons": reasons,
        "sources": {"taskset": args.taskset, "physics_contract": args.physics_contract, "repair_playbook": args.repair_playbook},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "success_count": success_count, "total_tasks": len(records)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
