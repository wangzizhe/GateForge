"""
Counterfactual trajectory runner for the v0.19.8 capability attribution pass.

Runs the frozen v0.19.5 benchmark through the real executor with the bounded
v0.19.7 residual repairs disabled. The output has the same summary shape as
the v0.19.5/v0.19.7 trajectory runners so it can be compared case by case.

Usage:
    python3 scripts/run_benchmark_counterfactual_v0_19_8.py [--benchmark JSONL] [--out-dir DIR]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from run_benchmark_trajectory_v0_19_5 import (
    EXECUTOR_MODULE,
    MAX_ROUNDS,
    REPO_ROOT,
    TIMEOUT_SEC,
    _aggregate,
    _load_cases,
    _summarise,
)

CANDIDATES_JSONL = REPO_ROOT / "artifacts" / "benchmark_v0_19_5" / "admitted_cases.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_counterfactual_v0_19_8"


def _run_case(case: dict, out_path: Path) -> dict:
    cmd = [
        sys.executable, "-m", EXECUTOR_MODULE,
        "--task-id", str(case.get("task_id") or case.get("candidate_id") or ""),
        "--failure-type", str(case.get("failure_type") or ""),
        "--expected-stage", str(case.get("expected_stage") or "simulate"),
        "--source-model-path", str(case.get("source_model_path") or ""),
        "--mutated-model-path", str(case.get("mutated_model_path") or ""),
        "--max-rounds", str(MAX_ROUNDS),
        "--timeout-sec", "240",
        "--simulate-stop-time", "0.1",
        "--simulate-intervals", "20",
        "--backend", "openmodelica_docker",
        "--planner-backend", "gemini",
        "--disable-bounded-residual-repairs", "on",
        "--out", str(out_path),
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
        return json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": f"json_parse_failed: {exc}"}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default=str(CANDIDATES_JSONL))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--n-cases", type=int, default=0)
    args = parser.parse_args()

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    raw_root = out_root / "raw"
    raw_root.mkdir(exist_ok=True)

    cases = _load_cases(Path(args.benchmark))
    if args.n_cases:
        cases = cases[:args.n_cases]
    print(f"Loaded {len(cases)} cases from benchmark.")
    print("Counterfactual: --disable-bounded-residual-repairs on\n")

    summaries = []
    for i, case in enumerate(cases, 1):
        cid = str(case.get("candidate_id") or f"case_{i}")
        print(f"[{i}/{len(cases)}] Running {cid}  failure_type={case.get('failure_type')}")
        out_path = raw_root / f"{cid}.json"
        payload = _run_case(case, out_path)
        summary = _summarise(case, payload)
        summary["counterfactual"] = "disable_bounded_residual_repairs"
        summaries.append(summary)

        status = summary.get("executor_status") or summary.get("status")
        print(
            f"  -> status={status}"
            f"  turns={summary.get('n_turns', '?')}"
            f"  termination={summary.get('termination', '?')}"
            f"  layer_transition={summary.get('saw_layer_transition', '?')}"
        )
        for turn, err in enumerate(summary.get("observed_error_sequence", []), 1):
            print(f"     turn {turn}: {err}")

    report = {
        "n_cases": len(summaries),
        "counterfactual": "disable_bounded_residual_repairs",
        "summaries": summaries,
    }
    report["aggregate"] = _aggregate(summaries)
    (out_root / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    aggregate = report["aggregate"]
    print("\n=== Aggregate ===")
    print(f"  total_cases: {aggregate['total_cases']}")
    print(f"  pass_rate: {aggregate['pass_rate']:.3f} ({aggregate['pass_count']}/{aggregate['total_cases']})")
    for family, group in sorted(aggregate["by_family"].items()):
        print(
            f"  {family}: pass_rate={group['pass_rate']:.3f} "
            f"avg_turns={group['avg_turns']:.2f} "
            f"pass={group['pass_count']}/{group['total_cases']}"
        )
    print(f"\nResults written to {out_root}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
