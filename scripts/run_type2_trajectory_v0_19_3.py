"""
Baseline trajectory runner for Type 2 inter-layer mutations (v0.19.3).

Runs the 3 Type 2 candidates (model_check_error → simulate_error masking chain)
through the real live executor and emits per-case turn-level summaries.

Type 2 design:
  - Turn 1: agent sees model_check_error (undefined variable), removes/fixes it
  - Turn 2: agent sees simulate_error (assert(false,...)), removes/fixes it
  - expected_stage=simulate so executor validates both checkModel AND simulate

Usage:
    python3 scripts/run_type2_trajectory_v0_19_3.py [--out-dir DIR]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_JSONL = REPO_ROOT / "artifacts" / "type2_mutations_v0_19_3" / "candidates.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "type2_trajectory_v0_19_3"
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


def _summarise(cid: str, payload: dict, expected_turns: int) -> dict:
    if "error" in payload:
        return {"candidate_id": cid, "status": "INFRA_FAIL", "error": payload["error"]}

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
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    raw_root = out_root / "raw"
    raw_root.mkdir(exist_ok=True)

    cases = _load_cases(CANDIDATES_JSONL)
    print(f"Loaded {len(cases)} cases from benchmark.\n")

    summaries = []
    for i, case in enumerate(cases, 1):
        cid = str(case.get("candidate_id") or f"case_{i}")
        print(f"[{i}/{len(cases)}] Running {cid}  failure_type={case.get('failure_type')}")
        out_path = raw_root / f"{cid}.json"
        payload = _run_case(case, out_path)
        summary = _summarise(cid, payload, case.get("expected_turns", 2))
        summaries.append(summary)

        status = summary.get("executor_status") or summary.get("status")
        print(f"  → status={status}"
              f"  turns={summary.get('n_turns', '?')}"
              f"  termination={summary.get('termination', '?')}"
              f"  layer_transition={summary.get('saw_layer_transition', '?')}")
        for t, err in enumerate(summary.get("observed_error_sequence", []), 1):
            print(f"     turn {t}: {err}")

    report = {"n_cases": len(summaries), "summaries": summaries}
    (out_root / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n=== Aggregate ===")
    terminations: dict[str, int] = {}
    layer_transitions = 0
    for s in summaries:
        t = s.get("termination") or s.get("status") or "unknown"
        terminations[t] = terminations.get(t, 0) + 1
        if s.get("saw_layer_transition"):
            layer_transitions += 1
    for k, v in sorted(terminations.items()):
        print(f"  {k}: {v}")
    avg_turns = (
        sum(s["n_turns"] for s in summaries if "n_turns" in s) / len(summaries)
        if summaries else 0
    )
    print(f"  avg_turns_per_case: {avg_turns:.2f}")
    print(f"  layer_transitions_seen: {layer_transitions}/{len(summaries)}")
    print(f"\nResults written to {out_root}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
