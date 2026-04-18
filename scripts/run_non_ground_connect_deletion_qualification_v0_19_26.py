"""Run trajectory qualification for structural connect-deletion cases.

Qualification policy:
  - Repeat each admitted candidate 3 times with the real LLM backend.
  - Use max_rounds=6.
  - Promote each candidate to one of:
      * multi_turn_core
      * anchor_single_fix
      * unresolved_hard
      * unstable_mixed
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK = (
    REPO_ROOT / "artifacts" / "non_ground_connect_deletion_mutations_v0_19_26" / "admitted_cases.jsonl"
)
DEFAULT_OUT_DIR = (
    REPO_ROOT / "artifacts" / "non_ground_connect_deletion_qualification_v0_19_26"
)
EXECUTOR_MODULE = "gateforge.agent_modelica_live_executor_v1"
REPEATS = 3
MAX_ROUNDS = 6
TIMEOUT_SEC = 420


def _load_cases(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _run_case(case: dict, *, out_path: Path, planner_backend: str) -> dict:
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
        "--backend", str(case.get("backend") or "openmodelica_docker"),
        "--planner-backend", planner_backend,
        "--workflow-goal", str(case.get("workflow_goal") or ""),
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
        return {"error": "subprocess_timeout"}
    if proc.returncode != 0 or not out_path.exists():
        return {
            "error": "executor_failed",
            "returncode": proc.returncode,
            "stderr": proc.stderr[-800:],
        }
    return json.loads(out_path.read_text(encoding="utf-8"))


def _effective_failure(attempt: dict) -> str:
    raw = str(attempt.get("observed_failure_type") or "")
    if raw and raw != "none":
        return raw
    if "physics_contract_pass" in attempt and not attempt["physics_contract_pass"]:
        return "behavioral_contract_fail"
    return "none"


def _summarise_payload(payload: dict) -> dict:
    if "error" in payload:
        return {
            "executor_status": "INFRA_FAIL",
            "turn_shape": "infra_fail",
            "n_turns": 0,
            "observed_error_sequence": [],
        }
    attempts = list(payload.get("attempts") or [])
    executor_status = str(payload.get("executor_status") or "").upper()
    observed_seq = [_effective_failure(a) for a in attempts]
    non_none = [e for e in observed_seq if e and e != "none"]
    if executor_status == "PASS" and len(non_none) == 1:
        turn_shape = "single_fix_closure"
    elif executor_status == "PASS" and len(non_none) > 1:
        turn_shape = "multi_turn_repair"
    elif executor_status == "PASS":
        turn_shape = "pass_no_repair_needed"
    else:
        turn_shape = "unresolved"
    return {
        "executor_status": executor_status,
        "turn_shape": turn_shape,
        "n_turns": len(attempts),
        "observed_error_sequence": observed_seq,
    }


def _dominant_sequence(summaries: list[dict]) -> tuple[str, int]:
    counts: dict[str, int] = {}
    for row in summaries:
        seq = " -> ".join(row.get("observed_error_sequence") or [])
        counts[seq] = counts.get(seq, 0) + 1
    if not counts:
        return "", 0
    seq, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return seq, count


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def classify_candidate(run_summaries: list[dict]) -> dict:
    multi_turn = sum(1 for row in run_summaries if row.get("turn_shape") == "multi_turn_repair")
    single_fix = sum(1 for row in run_summaries if row.get("turn_shape") == "single_fix_closure")
    unresolved = sum(1 for row in run_summaries if row.get("turn_shape") == "unresolved")
    median_turns = _median([int(row.get("n_turns") or 0) for row in run_summaries])
    dominant_seq, dominant_seq_count = _dominant_sequence(run_summaries)

    if multi_turn >= 2 and unresolved <= 1 and median_turns >= 3 and dominant_seq_count >= 2:
        label = "multi_turn_core"
    elif single_fix >= 2 and unresolved <= 1:
        label = "anchor_single_fix"
    elif unresolved >= 2:
        label = "unresolved_hard"
    else:
        label = "unstable_mixed"

    return {
        "qualification_label": label,
        "multi_turn_count": multi_turn,
        "single_fix_count": single_fix,
        "unresolved_count": unresolved,
        "median_turns": median_turns,
        "dominant_sequence": dominant_seq,
        "dominant_sequence_count": dominant_seq_count,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--planner-backend-override", default="auto")
    parser.add_argument("--report-version", default="v0.19.26")
    args = parser.parse_args()

    cases = _load_cases(Path(args.benchmark))
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "raw").mkdir(exist_ok=True)

    results = []
    for i, case in enumerate(cases, 1):
        cid = str(case.get("candidate_id") or f"case_{i}")
        print(f"[{i}/{len(cases)}] {cid}")
        run_summaries = []
        for rep in range(1, REPEATS + 1):
            out_path = out_root / "raw" / f"{cid}__run{rep}.json"
            case_copy = dict(case)
            case_copy["task_id"] = f"{cid}__run{rep}"
            payload = _run_case(
                case_copy,
                out_path=out_path,
                planner_backend=str(args.planner_backend_override or "auto"),
            )
            summary = _summarise_payload(payload)
            run_summaries.append(summary)
            print(
                f"  run {rep}: status={summary['executor_status']} "
                f"shape={summary['turn_shape']} turns={summary['n_turns']}"
            )
            for turn_idx, err in enumerate(summary.get("observed_error_sequence") or [], 1):
                print(f"    turn {turn_idx}: {err}")

        qualification = classify_candidate(run_summaries)
        row = {
            "candidate_id": cid,
            "source_file": case.get("source_file"),
            "deleted_connect": case.get("deleted_connect"),
            "deleted_connect_kind": case.get("deleted_connect_kind"),
            "deleted_connects": case.get("deleted_connects"),
            "deleted_connect_kinds": case.get("deleted_connect_kinds"),
            "deleted_component_line": case.get("deleted_component_line"),
            "deleted_component_instance": case.get("deleted_component_instance"),
            "deleted_component_kind": case.get("deleted_component_kind"),
            "deleted_component_connect_count": case.get("deleted_component_connect_count"),
            "expected_stage": case.get("expected_stage"),
            "run_summaries": run_summaries,
            **qualification,
        }
        results.append(row)
        print(
            f"  -> qualification={qualification['qualification_label']} "
            f"median_turns={qualification['median_turns']} "
            f"dominant_sequence={qualification['dominant_sequence']}"
        )

    label_counts: dict[str, int] = {}
    for row in results:
        label = str(row.get("qualification_label") or "")
        label_counts[label] = label_counts.get(label, 0) + 1

    report = {
        "version": str(args.report_version or "v0.19.26"),
        "n_cases": len(results),
        "planner_backend_override": str(args.planner_backend_override or "auto"),
        "qualification_label_counts": label_counts,
        "results": results,
    }
    (out_root / "qualification_summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Qualification Summary ===")
    print(json.dumps(report["qualification_label_counts"], indent=2, ensure_ascii=False))
    print(f"Results written to {out_root}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
