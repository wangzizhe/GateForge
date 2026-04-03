from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_v0_3_14_authority_eval_runner import run_authority_eval
from .agent_modelica_v0_3_14_replay_evidence import _first_attempt_cluster
from .agent_modelica_v0_3_14_step_experience_common import norm


SCHEMA_VERSION = "agent_modelica_v0_3_15_baseline_gate"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_PREVIEW_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_candidate_preview_current" / "admitted_taskset.json"
DEFAULT_EXPERIENCE_STORE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_authority_trace_extraction_current" / "experience_store.json"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_baseline_results_current"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_baseline_gate_current"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _summarize_rows(rows: list[dict]) -> dict:
    total = len(rows)
    passed_rows = [row for row in rows if norm(row.get("verdict")) == "PASS"]
    progressive_rows = [row for row in passed_rows if bool(row.get("progressive_solve"))]
    non_progress_rows = [row for row in rows if norm(row.get("verdict")) != "PASS" or not bool(row.get("progressive_solve"))]
    rounds = [int(row.get("rounds_used") or 0) for row in passed_rows if int(row.get("rounds_used") or 0) > 0]
    return {
        "total": total,
        "passed": len(passed_rows),
        "pass_rate_pct": round(100.0 * len(passed_rows) / float(total), 1) if total else 0.0,
        "progressive_solve_count": len(progressive_rows),
        "progressive_solve_rate_pct": round(100.0 * len(progressive_rows) / float(total), 1) if total else 0.0,
        "avg_rounds_on_pass": round(sum(rounds) / float(len(rounds)), 2) if rounds else 0.0,
        "dead_end_or_non_progress_count": len(non_progress_rows),
        "dead_end_or_non_progress_rate_pct": round(100.0 * len(non_progress_rows) / float(total), 1) if total else 0.0,
    }


def _coverage_lookup(experience_payload: dict) -> dict[tuple[str, str], int]:
    rows = experience_payload.get("step_records") if isinstance(experience_payload.get("step_records"), list) else []
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (norm(row.get("dominant_stage_subtype")), norm(row.get("residual_signal_cluster")))
        if not all(key):
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _build_retrieval_summary(baseline_summary: dict, experience_payload: dict) -> dict:
    counts = _coverage_lookup(experience_payload)
    tasks = []
    for row in baseline_summary.get("results") or []:
        if not isinstance(row, dict):
            continue
        stage_subtype, cluster = _first_attempt_cluster(str(row.get("result_json_path") or ""))
        step_count = counts.get((stage_subtype, cluster), 0)
        tasks.append(
            {
                "task_id": norm(row.get("task_id")),
                "dominant_stage_subtype": stage_subtype,
                "residual_signal_cluster": cluster,
                "exact_match_step_count": step_count,
                "exact_match_available": step_count > 0,
            }
        )
    ready_count = len([row for row in tasks if bool(row.get("exact_match_available"))])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "task_count": len(tasks),
        "exact_match_ready_count": ready_count,
        "exact_match_ready_rate_pct": round(100.0 * ready_count / float(len(tasks)), 1) if tasks else 0.0,
        "tasks": tasks,
    }


def _baseline_band_status(summary: dict) -> str:
    pass_rate = float(summary.get("pass_rate_pct") or 0.0)
    progressive_rate = float(summary.get("progressive_solve_rate_pct") or 0.0)
    dead_end_rate = float(summary.get("dead_end_or_non_progress_rate_pct") or 0.0)
    if pass_rate >= 95.0 and progressive_rate >= 95.0:
        return "baseline_saturated"
    if pass_rate < 25.0 and dead_end_rate >= 75.0:
        return "baseline_too_hard"
    if 25.0 <= pass_rate <= 85.0:
        return "baseline_in_band"
    return "baseline_out_of_band"


def run_baseline_gate(
    *,
    candidate_taskset_path: str = str(DEFAULT_CANDIDATE_PREVIEW_TASKSET),
    experience_store_path: str = str(DEFAULT_EXPERIENCE_STORE),
    results_out_dir: str = str(DEFAULT_RESULTS_DIR),
    out_dir: str = str(DEFAULT_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    experience_payload = _load_json(experience_store_path)
    baseline = run_authority_eval(
        taskset_path=candidate_taskset_path,
        results_out_dir=results_out_dir,
        out_dir=str(Path(out_dir) / "baseline"),
        evaluation_label="v0315_candidate_baseline",
        experience_source="",
        experience_replay="off",
        planner_experience_injection="off",
        planner_experience_max_tokens=400,
        timeout_sec=timeout_sec,
    )
    retrieval_summary = _build_retrieval_summary(baseline, experience_payload)
    ready_task_ids = {norm(row.get("task_id")) for row in retrieval_summary.get("tasks") or [] if bool(row.get("exact_match_available"))}
    admitted_rows = [row for row in baseline.get("results") or [] if isinstance(row, dict) and norm(row.get("task_id")) in ready_task_ids]
    admitted_summary = _summarize_rows(admitted_rows)
    baseline_band_status = _baseline_band_status(admitted_summary)
    retrieval_gate_status = (
        "retrieval_coverage_pass"
        if float(retrieval_summary.get("exact_match_ready_rate_pct") or 0.0) >= 60.0
        else "retrieval_coverage_fail"
    )
    decision = (
        "replay_sensitive_eval_ready"
        if baseline_band_status == "baseline_in_band" and retrieval_gate_status == "retrieval_coverage_pass"
        else "replay_sensitive_eval_not_ready"
    )
    admitted_taskset_payload = _load_json(candidate_taskset_path)
    admitted_task_rows = [
        row for row in (admitted_taskset_payload.get("tasks") or [])
        if isinstance(row, dict) and norm(row.get("task_id")) in ready_task_ids
    ]
    admitted_taskset = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if admitted_task_rows else "EMPTY",
        "task_count": len(admitted_task_rows),
        "task_ids": [row["task_id"] for row in admitted_task_rows],
        "tasks": admitted_task_rows,
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "candidate_taskset_path": str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path),
        "experience_store_path": str(Path(experience_store_path).resolve()) if Path(experience_store_path).exists() else str(experience_store_path),
        "baseline": baseline,
        "retrieval_summary": retrieval_summary,
        "admitted_baseline": admitted_summary,
        "baseline_band_status": baseline_band_status,
        "retrieval_gate_status": retrieval_gate_status,
        "admitted_eval_task_count": len(admitted_task_rows),
        "decision": decision,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", summary)
    _write_json(out_root / "admitted_eval_taskset.json", admitted_taskset)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.15 Baseline Saturation Gate",
                "",
                f"- decision: `{decision}`",
                f"- baseline_band_status: `{baseline_band_status}`",
                f"- retrieval_gate_status: `{retrieval_gate_status}`",
                f"- admitted_eval_task_count: `{len(admitted_task_rows)}`",
                "",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.15 baseline saturation gate.")
    parser.add_argument("--candidate-taskset", default=str(DEFAULT_CANDIDATE_PREVIEW_TASKSET))
    parser.add_argument("--experience-store", default=str(DEFAULT_EXPERIENCE_STORE))
    parser.add_argument("--results-out-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = run_baseline_gate(
        candidate_taskset_path=str(args.candidate_taskset),
        experience_store_path=str(args.experience_store),
        results_out_dir=str(args.results_out_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
