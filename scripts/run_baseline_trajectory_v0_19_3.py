"""
Baseline trajectory runner for v0.19.3 capability analysis.

Runs N cases from the v0.19.1 benchmark through the real live executor
(Docker + LLM) and emits a per-case turn-level summary.

Usage:
    python3 scripts/run_baseline_trajectory_v0_19_3.py [--n-cases N] [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK_JSONL = (
    REPO_ROOT / "artifacts" / "benchmark_v0_19_1" / "admitted_cases.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "baseline_trajectory_v0_19_3"
EXECUTOR_MODULE = "gateforge.agent_modelica_live_executor_v1"
MAX_ROUNDS = 8
TIMEOUT_SEC = 300  # per-case subprocess timeout (seconds)


def _load_cases(jsonl_path: Path, n: int, failure_type: str | None = None) -> list[dict]:
    cases = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            if failure_type and case.get("failure_type") != failure_type:
                continue
            cases.append(case)
            if len(cases) >= n:
                break
    return cases


def _run_case(case: dict, out_path: Path) -> dict:
    cmd = [
        sys.executable, "-m", EXECUTOR_MODULE,
        "--task-id",        str(case.get("task_id") or case.get("candidate_id") or ""),
        "--failure-type",   str(case.get("failure_type") or ""),
        "--expected-stage", str(case.get("expected_stage") or ""),
        "--source-model-path",  str(case.get("source_model_path") or ""),
        "--mutated-model-path", str(case.get("mutated_model_path") or ""),
        "--max-rounds",     str(MAX_ROUNDS),
        "--timeout-sec",    "180",
        "--simulate-stop-time", "0.2",
        "--simulate-intervals", "20",
        "--backend",        str(case.get("backend") or "openmodelica_docker"),
        "--planner-backend",str(case.get("planner_backend") or "gemini"),
        "--out",            str(out_path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=TIMEOUT_SEC,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"error": "subprocess_timeout", "returncode": None}

    if proc.returncode != 0 or not out_path.exists():
        return {
            "error": "executor_failed",
            "returncode": proc.returncode,
            "stderr": proc.stderr[-800:],
        }
    try:
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": f"json_parse_failed: {exc}"}
    return payload


def _summarise_payload(candidate_id: str, payload: dict) -> dict:
    if "error" in payload:
        return {
            "candidate_id": candidate_id,
            "status": "INFRA_FAIL",
            "error": payload["error"],
        }

    executor_status = str(payload.get("executor_status") or "").upper()
    attempts = list(payload.get("attempts") or [])
    n_turns = len(attempts)
    observed_sequence = [
        str(a.get("observed_failure_type") or "") for a in attempts
    ]
    final_error = observed_sequence[-1] if observed_sequence else ""

    # Derive termination reason
    if executor_status == "PASS":
        termination = "success"
    elif n_turns >= MAX_ROUNDS:
        termination = "timeout"
    elif n_turns >= 2 and observed_sequence[-1] == observed_sequence[-2]:
        termination = "stalled"
    else:
        termination = "cycling_or_early_stop"

    return {
        "candidate_id": candidate_id,
        "failure_type": str(payload.get("failure_type") or ""),
        "executor_status": executor_status,
        "n_turns": n_turns,
        "termination": termination,
        "observed_error_sequence": observed_sequence,
        "final_error": final_error,
        "llm_plan_failure_modes": [
            str(a.get("llm_plan_failure_mode") or "") for a in attempts
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real baseline trajectories for v0.19.3.")
    parser.add_argument("--n-cases", type=int, default=5, help="Number of cases to run (default: 5)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory")
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK_JSONL), help="Benchmark JSONL path")
    parser.add_argument("--failure-type", default="", help="Filter by failure_type (e.g. model_check_error)")
    args = parser.parse_args()

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    raw_root = out_root / "raw"
    raw_root.mkdir(exist_ok=True)

    failure_type_filter = str(args.failure_type).strip() or None
    cases = _load_cases(Path(args.benchmark), args.n_cases, failure_type=failure_type_filter)
    print(f"Loaded {len(cases)} cases from benchmark.")

    summaries = []
    for i, case in enumerate(cases, 1):
        cid = str(case.get("candidate_id") or f"case_{i}")
        print(f"\n[{i}/{len(cases)}] Running {cid}  failure_type={case.get('failure_type')}")
        out_path = raw_root / f"{cid}.json"
        payload = _run_case(case, out_path)
        summary = _summarise_payload(cid, payload)
        summaries.append(summary)
        # Print per-case result immediately
        print(f"  → status={summary.get('executor_status') or summary.get('status')}"
              f"  turns={summary.get('n_turns', '?')}"
              f"  termination={summary.get('termination', '?')}")
        if summary.get("observed_error_sequence"):
            for t, err in enumerate(summary["observed_error_sequence"], 1):
                print(f"     turn {t}: {err[:120]}")

    # Write summary
    report = {"n_cases": len(summaries), "summaries": summaries}
    report_path = out_root / "summary.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print aggregate
    print("\n=== Aggregate ===")
    terminations: dict[str, int] = {}
    for s in summaries:
        t = s.get("termination") or s.get("status") or "unknown"
        terminations[t] = terminations.get(t, 0) + 1
    for k, v in sorted(terminations.items()):
        print(f"  {k}: {v}")
    avg_turns = (
        sum(s["n_turns"] for s in summaries if "n_turns" in s) / len(summaries)
        if summaries else 0
    )
    print(f"  avg_turns_per_case: {avg_turns:.2f}")
    print(f"\nResults written to {out_root}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
