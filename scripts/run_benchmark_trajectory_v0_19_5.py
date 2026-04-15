"""
Unified trajectory runner for the v0.19.5 hardened mutation benchmark.

Runs Type 1 and Type 2 candidates through the real live executor and emits
aggregate metrics by family:
  - PASS rate
  - average turns by Type 1 / Type 2
  - layer transition observation rate for Type 2

Usage:
    python3 scripts/run_benchmark_trajectory_v0_19_5.py [--benchmark JSONL] [--out-dir DIR]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_JSONL = REPO_ROOT / "artifacts" / "benchmark_v0_19_5" / "admitted_cases.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_trajectory_v0_19_5"
EXECUTOR_MODULE = "gateforge.agent_modelica_live_executor_v1"
MAX_ROUNDS = 8
TIMEOUT_SEC = 360


def _load_cases(jsonl_path: Path) -> list[dict]:
    cases = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


def _run_case(case: dict, out_path: Path) -> dict:
    cmd = [
        sys.executable, "-m", EXECUTOR_MODULE,
        "--task-id",        str(case.get("task_id") or case.get("candidate_id") or ""),
        "--failure-type",   str(case.get("failure_type") or ""),
        "--expected-stage", str(case.get("expected_stage") or "simulate"),
        "--source-model-path",  str(case.get("source_model_path") or ""),
        "--mutated-model-path", str(case.get("mutated_model_path") or ""),
        "--max-rounds",     str(MAX_ROUNDS),
        "--timeout-sec",    "240",
        "--simulate-stop-time", "0.1",
        "--simulate-intervals", "20",
        "--backend",        "openmodelica_docker",
        "--planner-backend","gemini",
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
        return json.loads(out_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": f"json_parse_failed: {exc}"}


def _summarise(case: dict, payload: dict) -> dict:
    cid = str(case.get("candidate_id") or "")
    family = str(case.get("benchmark_family") or "")
    expected_turns = int(case.get("expected_turns") or 0)
    if "error" in payload:
        return {
            "candidate_id": cid,
            "benchmark_family": family,
            "benchmark_source": str(case.get("benchmark_source") or ""),
            "mutation_family": str(case.get("mutation_family") or family),
            "difficulty_prior": str(case.get("difficulty_prior") or ""),
            "status": "INFRA_FAIL",
            "error": payload["error"],
        }

    executor_status = str(payload.get("executor_status") or "").upper()
    attempts = list(payload.get("attempts") or [])
    n_turns = len(attempts)
    observed_seq = [str(a.get("observed_failure_type") or "") for a in attempts]

    if executor_status == "PASS":
        termination = "success"
    elif n_turns >= MAX_ROUNDS:
        termination = "max_rounds"
    elif n_turns >= 2 and observed_seq[-1] == observed_seq[-2]:
        termination = "stalled"
    else:
        termination = "cycling_or_early_stop"

    return {
        "candidate_id": cid,
        "benchmark_family": family,
        "benchmark_source": str(case.get("benchmark_source") or ""),
        "mutation_family": str(case.get("mutation_family") or family),
        "difficulty_prior": str(case.get("difficulty_prior") or ""),
        "failure_type": str(payload.get("failure_type") or ""),
        "executor_status": executor_status,
        "n_turns": n_turns,
        "expected_turns": expected_turns,
        "termination": termination,
        "observed_error_sequence": observed_seq,
        # Layer transition: agent progressed from model_check_error to a
        # simulation-phase failure (executor classifies assert(false,...) as
        # constraint_violation rather than simulate_error).
        "saw_layer_transition": (
            "model_check_error" in observed_seq
            and any(e in observed_seq for e in ("simulate_error", "constraint_violation"))
        ),
    }


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
    print(f"Loaded {len(cases)} cases from benchmark.\n")

    summaries = []
    for i, case in enumerate(cases, 1):
        cid = str(case.get("candidate_id") or f"case_{i}")
        print(f"[{i}/{len(cases)}] Running {cid}  failure_type={case.get('failure_type')}")
        out_path = raw_root / f"{cid}.json"
        payload = _run_case(case, out_path)
        summary = _summarise(case, payload)
        summaries.append(summary)

        status = summary.get("executor_status") or summary.get("status")
        print(f"  → status={status}"
              f"  turns={summary.get('n_turns', '?')}"
              f"  termination={summary.get('termination', '?')}"
              f"  layer_transition={summary.get('saw_layer_transition', '?')}")
        for t, err in enumerate(summary.get("observed_error_sequence", []), 1):
            print(f"     turn {t}: {err}")

    report = {"n_cases": len(summaries), "summaries": summaries}
    report["aggregate"] = _aggregate(summaries)
    (out_root / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n=== Aggregate ===")
    aggregate = report["aggregate"]
    print(f"  total_cases: {aggregate['total_cases']}")
    print(f"  pass_rate: {aggregate['pass_rate']:.3f} ({aggregate['pass_count']}/{aggregate['total_cases']})")
    for family, group in sorted(aggregate["by_family"].items()):
        print(
            f"  {family}: pass_rate={group['pass_rate']:.3f} "
            f"avg_turns={group['avg_turns']:.2f} "
            f"pass={group['pass_count']}/{group['total_cases']}"
        )
    type2 = aggregate["by_family"].get("type2_inter_layer")
    if type2:
        print(
            f"  type2_layer_transition_rate: {type2['layer_transition_rate']:.3f} "
            f"({type2['layer_transition_count']}/{type2['total_cases']})"
        )
    print("  difficulty_profile:")
    for bucket, group in sorted(aggregate["by_difficulty_bucket"].items()):
        print(
            f"    {bucket}: total={group['total_cases']} pass_rate={group['pass_rate']:.3f} "
            f"avg_turns={group['avg_turns']:.2f}"
        )
    print(f"\nResults written to {out_root}/")
    return 0


def _avg(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def _aggregate(summaries: list[dict]) -> dict:
    total = len(summaries)
    pass_count = sum(1 for s in summaries if s.get("executor_status") == "PASS")
    by_family: dict[str, dict] = {}
    by_difficulty_bucket: dict[str, dict] = {}

    for summary in summaries:
        family = str(summary.get("benchmark_family") or "unknown")
        _add_to_group(by_family, family, summary)
        bucket = _difficulty_bucket(summary)
        _add_to_group(by_difficulty_bucket, bucket, summary)

    return {
        "total_cases": total,
        "pass_count": pass_count,
        "pass_rate": pass_count / total if total else 0.0,
        "by_family": _compact_groups(by_family),
        "by_difficulty_bucket": _compact_groups(by_difficulty_bucket),
    }


def _add_to_group(groups: dict[str, dict], key: str, summary: dict) -> None:
    group = groups.setdefault(
        key,
        {
            "total_cases": 0,
            "pass_count": 0,
            "turns": [],
            "layer_transition_count": 0,
            "terminations": {},
        },
    )
    group["total_cases"] += 1
    if summary.get("executor_status") == "PASS":
        group["pass_count"] += 1
    if "n_turns" in summary:
        group["turns"].append(int(summary["n_turns"]))
    if summary.get("saw_layer_transition"):
        group["layer_transition_count"] += 1
    termination = str(summary.get("termination") or summary.get("status") or "unknown")
    group["terminations"][termination] = group["terminations"].get(termination, 0) + 1


def _compact_groups(groups: dict[str, dict]) -> dict[str, dict]:
    compact = {}
    for key, group in groups.items():
        group_total = group["total_cases"]
        layer_count = group["layer_transition_count"]
        compact[key] = {
            "total_cases": group_total,
            "pass_count": group["pass_count"],
            "pass_rate": group["pass_count"] / group_total if group_total else 0.0,
            "avg_turns": _avg(group["turns"]),
            "layer_transition_count": layer_count,
            "layer_transition_rate": layer_count / group_total if group_total else 0.0,
            "terminations": group["terminations"],
        }
    return compact


def _difficulty_bucket(summary: dict) -> str:
    if summary.get("status") == "INFRA_FAIL":
        return "infra_fail"
    if summary.get("executor_status") != "PASS":
        return "too_hard_or_unresolved"
    n_turns = int(summary.get("n_turns") or 0)
    if n_turns <= 1:
        return "too_easy"
    if n_turns <= 4:
        return "target_difficulty"
    return "hard_but_solved"


if __name__ == "__main__":
    raise SystemExit(main())
