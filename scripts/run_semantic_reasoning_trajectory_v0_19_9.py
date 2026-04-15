"""
Run the v0.19.9 semantic reasoning benchmark through the live executor.

By default this is the normal run. Use
``--disable-bounded-residual-repairs on`` for the required counterfactual pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from run_benchmark_trajectory_v0_19_5 import _aggregate, _load_cases, _summarise

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_JSONL = REPO_ROOT / "artifacts" / "semantic_reasoning_mutations_v0_19_9" / "admitted_cases.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_reasoning_trajectory_v0_19_9"
EXECUTOR_MODULE = "gateforge.agent_modelica_live_executor_v1"
MAX_ROUNDS = 5
TIMEOUT_SEC = 420


def _run_case(case: dict, out_path: Path, *, disable_bounded_residual_repairs: str) -> dict:
    cmd = [
        sys.executable, "-m", EXECUTOR_MODULE,
        "--task-id", str(case.get("task_id") or case.get("candidate_id") or ""),
        "--failure-type", str(case.get("failure_type") or ""),
        "--expected-stage", str(case.get("expected_stage") or "simulate"),
        "--workflow-goal", str(case.get("workflow_goal") or ""),
        "--source-model-path", str(case.get("source_model_path") or ""),
        "--mutated-model-path", str(case.get("mutated_model_path") or ""),
        "--max-rounds", str(MAX_ROUNDS),
        "--timeout-sec", "240",
        "--simulate-stop-time", "0.1",
        "--simulate-intervals", "20",
        "--backend", "openmodelica_docker",
        "--planner-backend", "gemini",
        "--disable-bounded-residual-repairs", disable_bounded_residual_repairs,
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
    parser.add_argument("--disable-bounded-residual-repairs", choices=["on", "off"], default="off")
    args = parser.parse_args()

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    raw_root = out_root / "raw"
    raw_root.mkdir(exist_ok=True)

    cases = _load_cases(Path(args.benchmark))
    print(f"Loaded {len(cases)} semantic reasoning cases.")
    print(f"disable_bounded_residual_repairs={args.disable_bounded_residual_repairs}\n")

    summaries = []
    for i, case in enumerate(cases, 1):
        cid = str(case.get("candidate_id") or f"case_{i}")
        print(f"[{i}/{len(cases)}] Running {cid}")
        payload = _run_case(
            case,
            raw_root / f"{cid}.json",
            disable_bounded_residual_repairs=str(args.disable_bounded_residual_repairs),
        )
        summary = _summarise(case, payload)
        summary["requires_nonlocal_or_semantic_reasoning"] = bool(case.get("requires_nonlocal_or_semantic_reasoning"))
        summary["omc_localization_sufficient"] = bool(case.get("omc_localization_sufficient"))
        summaries.append(summary)
        status = summary.get("executor_status") or summary.get("status")
        print(f"  -> status={status} turns={summary.get('n_turns', '?')} termination={summary.get('termination', '?')}")
        for turn, err in enumerate(summary.get("observed_error_sequence", []), 1):
            print(f"     turn {turn}: {err}")

    report = {
        "version": "v0.19.9",
        "disable_bounded_residual_repairs": str(args.disable_bounded_residual_repairs),
        "n_cases": len(summaries),
        "summaries": summaries,
    }
    report["aggregate"] = _aggregate(summaries)
    (out_root / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    aggregate = report["aggregate"]
    print("\n=== Aggregate ===")
    print(f"  pass_rate: {aggregate['pass_rate']:.3f} ({aggregate['pass_count']}/{aggregate['total_cases']})")
    print(f"Results written to {out_root}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
