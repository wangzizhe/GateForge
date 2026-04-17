"""
Unified trajectory runner for GateForge Benchmark v1.

Handles all error layers in a single pass:
  Layer 2 (structural-observable): constraint_violation cases
  Layer 3 (behavioral-only):       semantic oracle cases

Usage:
    python3 scripts/run_benchmark_trajectory_gf_v1.py [--out-dir DIR]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK = REPO_ROOT / "artifacts" / "benchmark_gf_v1" / "admitted_cases.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1"
EXECUTOR_MODULE = "gateforge.agent_modelica_live_executor_v1"
MAX_ROUNDS = 6
TIMEOUT_SEC = 420


def _load_cases(path: Path) -> list[dict]:
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _run_case(case: dict, out_path: Path, planner_backend_override: str = "") -> dict:
    planner_backend = str(planner_backend_override or case.get("planner_backend") or "gemini")
    cmd = [
        sys.executable, "-m", EXECUTOR_MODULE,
        "--task-id",            str(case.get("task_id") or case.get("candidate_id") or ""),
        "--failure-type",       str(case.get("failure_type") or ""),
        "--expected-stage",     str(case.get("expected_stage") or "simulate"),
        "--source-model-path",  str(case.get("source_model_path") or ""),
        "--mutated-model-path", str(case.get("mutated_model_path") or ""),
        "--max-rounds",         str(MAX_ROUNDS),
        "--timeout-sec",        "240",
        "--simulate-stop-time", "0.1",
        "--simulate-intervals", "20",
        "--backend",            str(case.get("backend") or "openmodelica_docker"),
        "--planner-backend",    planner_backend,
        "--out",                str(out_path),
    ]
    # Layer 3 cases carry a workflow_goal that the executor uses as semantic context
    workflow_goal = str(case.get("workflow_goal") or "").strip()
    if workflow_goal:
        cmd += ["--workflow-goal", workflow_goal]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, check=False,
            timeout=TIMEOUT_SEC, cwd=str(REPO_ROOT),
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
    if "error" in payload:
        return {
            "candidate_id": cid,
            "benchmark_family": case.get("benchmark_family", ""),
            "error_layer": case.get("error_layer"),
            "status": "INFRA_FAIL",
            "error": payload["error"],
        }

    executor_status = str(payload.get("executor_status") or "").upper()
    attempts = list(payload.get("attempts") or [])
    n_turns = len(attempts)

    # Build observed error sequence. For layer-3 (behavioral) cases the OMC
    # check/simulate both pass so observed_failure_type stays "none", but the
    # behavioral oracle sets physics_contract_pass=False on the failing rounds.
    # Promote those rounds to "behavioral_contract_fail" so turn-shape
    # classification correctly sees the repair signal.
    def _effective_failure(a: dict) -> str:
        raw = str(a.get("observed_failure_type") or "")
        if raw and raw != "none":
            return raw
        # OMC passed but oracle failed — behavioral layer error
        if "physics_contract_pass" in a and not a["physics_contract_pass"]:
            return "behavioral_contract_fail"
        return "none"

    observed_seq = [_effective_failure(a) for a in attempts]

    # Classify turn shape: was this a single-fix-closure or genuine multi-turn?
    # single_fix_closure: exactly one non-none error then success
    non_none = [e for e in observed_seq if e and e != "none"]
    if executor_status == "PASS" and len(non_none) == 1:
        turn_shape = "single_fix_closure"
    elif executor_status == "PASS" and len(non_none) > 1:
        turn_shape = "multi_turn_repair"
    elif executor_status == "PASS" and len(non_none) == 0:
        # PASS with no observed errors: behavioral oracle passed from round 1,
        # meaning the mutated model was already correct — likely an oracle or
        # admission issue.
        turn_shape = "pass_no_repair_needed"
    else:
        turn_shape = "unresolved"

    return {
        "candidate_id": cid,
        "benchmark_family": case.get("benchmark_family", ""),
        "error_layer": case.get("error_layer"),
        "mutation_mechanism": case.get("mutation_mechanism", ""),
        "executor_status": executor_status,
        "n_turns": n_turns,
        "turn_shape": turn_shape,
        "observed_error_sequence": observed_seq,
    }


def _aggregate(summaries: list[dict]) -> dict:
    total = len(summaries)
    passed = sum(1 for s in summaries if s.get("executor_status") == "PASS")

    by_family: dict[str, dict] = {}
    by_layer: dict[str, dict] = {}
    turn_shapes: dict[str, int] = {}

    for s in summaries:
        fam = s.get("benchmark_family") or "unknown"
        layer = str(s.get("error_layer") or "?")
        shape = s.get("turn_shape") or "unknown"

        for bucket, key in [(by_family, fam), (by_layer, layer)]:
            if key not in bucket:
                bucket[key] = {"total": 0, "pass": 0, "turns": []}
            bucket[key]["total"] += 1
            if s.get("executor_status") == "PASS":
                bucket[key]["pass"] += 1
            if "n_turns" in s:
                bucket[key]["turns"].append(s["n_turns"])

        turn_shapes[shape] = turn_shapes.get(shape, 0) + 1

    def _finalise(d: dict) -> dict:
        return {
            k: {
                "total": v["total"],
                "pass_rate": round(v["pass"] / v["total"], 3) if v["total"] else 0,
                "avg_turns": round(sum(v["turns"]) / len(v["turns"]), 2) if v["turns"] else 0,
            }
            for k, v in d.items()
        }

    return {
        "total_cases": total,
        "pass_count": passed,
        "pass_rate": round(passed / total, 3) if total else 0,
        "by_family": _finalise(by_family),
        "by_error_layer": _finalise(by_layer),
        "turn_shape_counts": turn_shapes,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--planner-backend-override",
        default="",
        help="Override per-case planner_backend, e.g. auto or minimax",
    )
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip cases whose raw output JSON already exists")
    args = parser.parse_args()

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "raw").mkdir(exist_ok=True)

    cases = _load_cases(Path(args.benchmark))
    print(f"Loaded {len(cases)} cases from {args.benchmark}\n")

    summaries = []
    for i, case in enumerate(cases, 1):
        cid = str(case.get("candidate_id") or f"case_{i}")
        layer = case.get("error_layer", "?")
        family = case.get("benchmark_family", "")
        out_path = out_root / "raw" / f"{cid}.json"
        print(f"[{i}/{len(cases)}] {cid}  layer={layer}  family={family}")
        if args.skip_existing and out_path.exists():
            print(f"  -> [skipped, using cached result]")
            try:
                payload = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {"error": "cached_json_unreadable"}
        else:
            payload = _run_case(
                case,
                out_path,
                planner_backend_override=str(args.planner_backend_override or "").strip(),
            )
        summary = _summarise(case, payload)
        summaries.append(summary)
        print(f"  -> status={summary.get('executor_status') or summary.get('status')}"
              f"  turns={summary.get('n_turns', '?')}"
              f"  shape={summary.get('turn_shape', '?')}")
        for t, err in enumerate(summary.get("observed_error_sequence", []), 1):
            print(f"     turn {t}: {err}")

    aggregate = _aggregate(summaries)
    report = {
        "benchmark_version": "gf_v1",
        "n_cases": len(summaries),
        "aggregate": aggregate,
        "summaries": summaries,
    }
    (out_root / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n=== Aggregate ===")
    print(f"  pass_rate: {aggregate['pass_rate']:.3f} ({aggregate['pass_count']}/{aggregate['total_cases']})")
    print(f"  turn_shapes: {aggregate['turn_shape_counts']}")
    print(f"\n  by_family:")
    for fam, stats in sorted(aggregate["by_family"].items()):
        print(f"    {fam}: pass_rate={stats['pass_rate']} avg_turns={stats['avg_turns']}")
    print(f"\n  by_error_layer:")
    for layer, stats in sorted(aggregate["by_error_layer"].items()):
        print(f"    layer {layer}: pass_rate={stats['pass_rate']} avg_turns={stats['avg_turns']}")
    print(f"\nResults written to {out_root}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
