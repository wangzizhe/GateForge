from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_v0_3_14_authority_eval_runner import run_authority_eval
from .agent_modelica_v0_3_14_step_experience_common import norm, residual_signal_cluster


SCHEMA_VERSION = "agent_modelica_v0_3_14_replay_evidence"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_authority_manifest_current" / "manifest.json"
DEFAULT_EXPERIENCE_STORE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_authority_trace_extraction_current" / "experience_store.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_replay_evidence_current"


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


def _first_attempt_cluster(result_json_path: str) -> tuple[str, str]:
    detail = _load_json(result_json_path)
    attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
    first_attempt = next((row for row in attempts if isinstance(row, dict)), {})
    diagnostic = first_attempt.get("diagnostic_ir") if isinstance(first_attempt.get("diagnostic_ir"), dict) else {}
    stage_subtype = norm(diagnostic.get("dominant_stage_subtype") or detail.get("dominant_stage_subtype"))
    cluster = residual_signal_cluster(
        dominant_stage_subtype=stage_subtype,
        error_subtype=norm(diagnostic.get("error_subtype")),
        observed_failure_type=norm(first_attempt.get("observed_failure_type") or detail.get("failure_type")),
        reason=norm(first_attempt.get("reason")),
    )
    return stage_subtype, cluster


def _build_retrieval_summary(manifest: dict, experience_store: dict) -> dict:
    step_rows = [row for row in (experience_store.get("step_records") or []) if isinstance(row, dict)]
    by_key: dict[tuple[str, str], int] = {}
    for row in step_rows:
        key = (norm(row.get("dominant_stage_subtype")), norm(row.get("residual_signal_cluster")))
        by_key[key] = by_key.get(key, 0) + 1
    task_rows = []
    for section_name in ("runtime", "initialization"):
        section = manifest.get(section_name) if isinstance(manifest.get(section_name), dict) else {}
        for entry in section.get("eval_tasks") or []:
            if not isinstance(entry, dict):
                continue
            stage_subtype, cluster = _first_attempt_cluster(norm(entry.get("result_json_path")))
            key = (stage_subtype, cluster)
            task_rows.append(
                {
                    "task_id": norm(entry.get("task_id")),
                    "lane_name": norm(entry.get("lane_name")),
                    "dominant_stage_subtype": stage_subtype,
                    "residual_signal_cluster": cluster,
                    "exact_match_step_count": by_key.get(key, 0),
                    "exact_match_available": by_key.get(key, 0) > 0,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "eval_task_count": len(task_rows),
        "exact_match_ready_count": len([row for row in task_rows if bool(row.get("exact_match_available"))]),
        "exact_match_ready_rate_pct": round(
            100.0 * len([row for row in task_rows if bool(row.get("exact_match_available"))]) / float(len(task_rows)),
            1,
        )
        if task_rows
        else 0.0,
        "tasks": task_rows,
    }


def _metric_delta(baseline: dict, replay: dict) -> dict:
    return {
        "success_rate_pct_delta": round(float(replay.get("pass_rate_pct") or 0.0) - float(baseline.get("pass_rate_pct") or 0.0), 1),
        "progressive_solve_rate_pct_delta": round(float(replay.get("progressive_solve_rate_pct") or 0.0) - float(baseline.get("progressive_solve_rate_pct") or 0.0), 1),
        "avg_rounds_on_pass_delta": round(float(replay.get("avg_rounds_on_pass") or 0.0) - float(baseline.get("avg_rounds_on_pass") or 0.0), 2),
        "dead_end_or_non_progress_rate_pct_delta": round(
            float(replay.get("dead_end_or_non_progress_rate_pct") or 0.0) - float(baseline.get("dead_end_or_non_progress_rate_pct") or 0.0),
            1,
        ),
    }


def _decide(runtime_baseline: dict, runtime_replay: dict) -> str:
    success_gain = float(runtime_replay.get("pass_rate_pct") or 0.0) > float(runtime_baseline.get("pass_rate_pct") or 0.0)
    progressive_gain = float(runtime_replay.get("progressive_solve_rate_pct") or 0.0) > float(runtime_baseline.get("progressive_solve_rate_pct") or 0.0)
    rounds_gain = (
        float(runtime_replay.get("avg_rounds_on_pass") or 0.0) < float(runtime_baseline.get("avg_rounds_on_pass") or 0.0)
        and float(runtime_replay.get("pass_rate_pct") or 0.0) >= float(runtime_baseline.get("pass_rate_pct") or 0.0)
    )
    replay_hit = float(runtime_replay.get("replay_hit_rate_pct") or 0.0) > 0.0
    if replay_hit and (success_gain or progressive_gain or rounds_gain):
        return "replay_gain_confirmed"
    if replay_hit:
        return "replay_operational_but_no_clear_gain"
    return "replay_not_yet_operational"


def run_replay_evidence(
    *,
    manifest_path: str = str(DEFAULT_MANIFEST),
    experience_store_path: str = str(DEFAULT_EXPERIENCE_STORE),
    out_dir: str = str(DEFAULT_OUT_DIR),
    planner_experience_max_tokens: int = 400,
    timeout_sec: int = 600,
) -> dict:
    manifest = _load_json(manifest_path)
    experience_store = _load_json(experience_store_path)
    runtime_taskset = norm(((manifest.get("runtime") or {}).get("eval_taskset_path")))
    initialization_taskset = norm(((manifest.get("initialization") or {}).get("eval_taskset_path")))
    if not runtime_taskset or not initialization_taskset:
        raise RuntimeError("missing_v0_3_14_eval_tasksets")
    retrieval_summary = _build_retrieval_summary(manifest, experience_store)
    out_root = Path(out_dir)
    runtime_baseline = run_authority_eval(
        taskset_path=runtime_taskset,
        results_out_dir=str(out_root / "runtime_baseline_results"),
        out_dir=str(out_root / "runtime_baseline"),
        evaluation_label="runtime_baseline",
        experience_source="",
        experience_replay="off",
        planner_experience_injection="off",
        planner_experience_max_tokens=planner_experience_max_tokens,
        timeout_sec=timeout_sec,
    )
    runtime_replay = run_authority_eval(
        taskset_path=runtime_taskset,
        results_out_dir=str(out_root / "runtime_replay_results"),
        out_dir=str(out_root / "runtime_replay"),
        evaluation_label="runtime_replay",
        experience_source=str(Path(experience_store_path).resolve()),
        experience_replay="on",
        planner_experience_injection="on",
        planner_experience_max_tokens=planner_experience_max_tokens,
        timeout_sec=timeout_sec,
    )
    initialization_baseline = run_authority_eval(
        taskset_path=initialization_taskset,
        results_out_dir=str(out_root / "initialization_baseline_results"),
        out_dir=str(out_root / "initialization_baseline"),
        evaluation_label="initialization_baseline",
        experience_source="",
        experience_replay="off",
        planner_experience_injection="off",
        planner_experience_max_tokens=planner_experience_max_tokens,
        timeout_sec=timeout_sec,
    )
    initialization_replay = run_authority_eval(
        taskset_path=initialization_taskset,
        results_out_dir=str(out_root / "initialization_replay_results"),
        out_dir=str(out_root / "initialization_replay"),
        evaluation_label="initialization_replay",
        experience_source=str(Path(experience_store_path).resolve()),
        experience_replay="on",
        planner_experience_injection="on",
        planner_experience_max_tokens=planner_experience_max_tokens,
        timeout_sec=timeout_sec,
    )
    injection_summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "runtime_replay_hit_rate_pct": float(runtime_replay.get("replay_hit_rate_pct") or 0.0),
        "initialization_replay_hit_rate_pct": float(initialization_replay.get("replay_hit_rate_pct") or 0.0),
        "runtime_experience_replay_hit_count": int(runtime_replay.get("experience_replay_hit_count") or 0),
        "runtime_planner_hint_hit_count": int(runtime_replay.get("planner_hint_hit_count") or 0),
        "initialization_experience_replay_hit_count": int(initialization_replay.get("experience_replay_hit_count") or 0),
        "initialization_planner_hint_hit_count": int(initialization_replay.get("planner_hint_hit_count") or 0),
    }
    decision = _decide(runtime_baseline, runtime_replay)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "manifest_path": str(Path(manifest_path).resolve()) if Path(manifest_path).exists() else str(manifest_path),
        "experience_store_path": str(Path(experience_store_path).resolve()) if Path(experience_store_path).exists() else str(experience_store_path),
        "retrieval_summary": retrieval_summary,
        "injection_summary": injection_summary,
        "runtime": {
            "baseline": runtime_baseline,
            "replay": runtime_replay,
            "delta": _metric_delta(runtime_baseline, runtime_replay),
        },
        "initialization": {
            "baseline": initialization_baseline,
            "replay": initialization_replay,
            "delta": _metric_delta(initialization_baseline, initialization_replay),
        },
        "version_decision": decision,
    }
    _write_json(out_root / "retrieval_summary.json", retrieval_summary)
    _write_json(out_root / "injection_summary.json", injection_summary)
    _write_json(out_root / "summary.json", summary)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.14 Replay Evidence",
                "",
                f"- version_decision: `{decision}`",
                f"- runtime_success_rate_pct_delta: `{summary['runtime']['delta']['success_rate_pct_delta']}`",
                f"- runtime_progressive_solve_rate_pct_delta: `{summary['runtime']['delta']['progressive_solve_rate_pct_delta']}`",
                f"- runtime_replay_hit_rate_pct: `{runtime_replay.get('replay_hit_rate_pct')}`",
                "",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.3.14 replay evidence on authority eval slices.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--experience-store", default=str(DEFAULT_EXPERIENCE_STORE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--planner-experience-max-tokens", type=int, default=400)
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = run_replay_evidence(
        manifest_path=str(args.manifest),
        experience_store_path=str(args.experience_store),
        out_dir=str(args.out_dir),
        planner_experience_max_tokens=int(args.planner_experience_max_tokens or 0),
        timeout_sec=int(args.timeout_sec),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "version_decision": payload.get("version_decision"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
