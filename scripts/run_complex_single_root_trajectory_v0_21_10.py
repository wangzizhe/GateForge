#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK = REPO_ROOT / "artifacts" / "complex_single_root_repair_benchmark_v0_21_10" / "admitted_cases.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "complex_single_root_repair_trajectory_v0_21_10_strict"
EXECUTOR_MODULE = "gateforge.agent_modelica_live_executor_v1"


def load_cases(path: Path) -> list[dict]:
    rows: list[dict] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def run_case(case: dict, out_path: Path, *, max_rounds: int, timeout_sec: int) -> dict:
    cmd = [
        sys.executable,
        "-m",
        EXECUTOR_MODULE,
        "--task-id",
        str(case.get("task_id") or case.get("candidate_id") or ""),
        "--failure-type",
        str(case.get("failure_type") or ""),
        "--expected-stage",
        str(case.get("expected_stage") or "check"),
        "--workflow-goal",
        str(case.get("workflow_goal") or ""),
        "--source-model-path",
        str(case.get("source_model_path") or ""),
        "--mutated-model-path",
        str(case.get("mutated_model_path") or ""),
        "--max-rounds",
        str(max_rounds),
        "--timeout-sec",
        "240",
        "--simulate-stop-time",
        "0.1",
        "--simulate-intervals",
        "20",
        "--backend",
        "openmodelica_docker",
        "--planner-backend",
        "gemini",
        "--remedy-pack-enabled",
        "off",
        "--capability-intervention-pack-enabled",
        "off",
        "--broader-change-pack-enabled",
        "off",
        "--experience-replay",
        "off",
        "--planner-experience-injection",
        "off",
        "--out",
        str(out_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"error": "subprocess_timeout", "returncode": None}
    if proc.returncode != 0 or not out_path.exists():
        return {
            "error": "executor_failed",
            "returncode": proc.returncode,
            "stderr": proc.stderr[-1200:],
            "stdout": proc.stdout[-1200:],
        }
    return json.loads(out_path.read_text(encoding="utf-8"))


def summarize_case(case: dict, payload: dict, *, max_rounds: int) -> dict:
    candidate_id = str(case.get("candidate_id") or "")
    if payload.get("error"):
        return {
            "candidate_id": candidate_id,
            "mutation_family": str(case.get("mutation_family") or ""),
            "executor_status": "INFRA_FAIL",
            "error": payload.get("error"),
        }
    attempts = list(payload.get("attempts") or [])
    observed = [str(row.get("observed_failure_type") or "") for row in attempts]
    executor_status = str(payload.get("executor_status") or "").upper()
    status = "PASS" if executor_status == "PASS" else "FAILED"
    if status == "PASS":
        termination = "success"
    elif len(attempts) >= max_rounds:
        termination = "max_rounds"
    elif len(observed) >= 2 and observed[-1] == observed[-2]:
        termination = "stalled"
    else:
        termination = "early_stop"
    layer_transition = (
        "model_check_error" in observed
        and any(item in observed for item in ("constraint_violation", "simulate_error", "none"))
    )
    return {
        "candidate_id": candidate_id,
        "mutation_family": str(case.get("mutation_family") or ""),
        "executor_status": status,
        "n_turns": len(attempts),
        "termination": termination,
        "observed_error_sequence": observed,
        "saw_layer_transition": layer_transition,
        "remedy_pack_enabled": bool(payload.get("remedy_pack_enabled")),
        "capability_intervention_pack_enabled": bool(payload.get("capability_intervention_pack_enabled")),
        "broader_change_pack_enabled": bool(payload.get("broader_change_pack_enabled")),
        "experience_replay_used": bool((payload.get("experience_replay") or {}).get("used")),
        "planner_experience_injection_used": bool((payload.get("planner_experience_injection") or {}).get("used")),
    }


def aggregate(summaries: list[dict]) -> dict:
    valid = [row for row in summaries if row.get("executor_status") != "INFRA_FAIL"]
    pass_rows = [row for row in valid if row.get("executor_status") == "PASS"]
    multiturn_pass_rows = [
        row for row in pass_rows if int(row.get("n_turns") or 0) >= 3 and row.get("saw_layer_transition")
    ]
    return {
        "total_cases": len(valid),
        "pass_count": len(pass_rows),
        "pass_rate": len(pass_rows) / len(valid) if valid else 0.0,
        "multiturn_pass_count": len(multiturn_pass_rows),
        "multiturn_pass_rate": len(multiturn_pass_rows) / len(valid) if valid else 0.0,
        "strict_no_auxiliary_packs": all(
            not row.get("remedy_pack_enabled")
            and not row.get("capability_intervention_pack_enabled")
            and not row.get("broader_change_pack_enabled")
            and not row.get("experience_replay_used")
            and not row.get("planner_experience_injection_used")
            for row in valid
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strict v0.21.10 complex single-root trajectories.")
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--timeout-sec", type=int, default=420)
    args = parser.parse_args()

    cases = load_cases(Path(args.benchmark))
    out_dir = Path(args.out_dir)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict] = []
    print(f"Loaded {len(cases)} cases from benchmark.")
    for index, case in enumerate(cases, start=1):
        candidate_id = str(case.get("candidate_id") or f"case_{index}")
        print(f"[{index}/{len(cases)}] Running {candidate_id}")
        raw_path = raw_dir / f"{candidate_id}.json"
        payload = run_case(case, raw_path, max_rounds=args.max_rounds, timeout_sec=args.timeout_sec)
        summary = summarize_case(case, payload, max_rounds=args.max_rounds)
        summaries.append(summary)
        print(
            "  status={status} turns={turns} termination={termination} transition={transition}".format(
                status=summary.get("executor_status"),
                turns=summary.get("n_turns"),
                termination=summary.get("termination"),
                transition=summary.get("saw_layer_transition"),
            )
        )
    report = {
        "version": "v0.21.10",
        "discipline": "agent_llm_omc_only_no_deterministic_repair",
        "summaries": summaries,
        "aggregate": aggregate(summaries),
    }
    (out_dir / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    agg = report["aggregate"]
    print(
        "aggregate pass={pass_count}/{total} multiturn={multi} strict={strict}".format(
            pass_count=agg["pass_count"],
            total=agg["total_cases"],
            multi=agg["multiturn_pass_count"],
            strict=agg["strict_no_auxiliary_packs"],
        )
    )
    return 0 if agg["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
