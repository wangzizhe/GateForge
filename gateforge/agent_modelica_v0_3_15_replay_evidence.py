from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_v0_3_14_authority_eval_runner import run_authority_eval


SCHEMA_VERSION = "agent_modelica_v0_3_15_replay_evidence"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE_GATE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_baseline_gate_current" / "summary.json"
DEFAULT_ADMITTED_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_baseline_gate_current" / "admitted_eval_taskset.json"
DEFAULT_EXPERIENCE_STORE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_authority_trace_extraction_current" / "experience_store.json"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_replay_results_current"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_replay_evidence_current"


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


def _decide(baseline_gate: dict, replay: dict) -> str:
    if str(baseline_gate.get("decision") or "") != "replay_sensitive_eval_ready":
        return "replay_sensitive_eval_not_ready"
    replay_hit = float(replay.get("replay_hit_rate_pct") or 0.0) > 0.0
    success_gain = float(replay.get("pass_rate_pct") or 0.0) > float((baseline_gate.get("admitted_baseline") or {}).get("pass_rate_pct") or 0.0)
    progressive_gain = float(replay.get("progressive_solve_rate_pct") or 0.0) > float((baseline_gate.get("admitted_baseline") or {}).get("progressive_solve_rate_pct") or 0.0)
    rounds_gain = (
        float(replay.get("avg_rounds_on_pass") or 0.0) < float((baseline_gate.get("admitted_baseline") or {}).get("avg_rounds_on_pass") or 0.0)
        and float(replay.get("pass_rate_pct") or 0.0) >= float((baseline_gate.get("admitted_baseline") or {}).get("pass_rate_pct") or 0.0)
    )
    if replay_hit and (success_gain or progressive_gain or rounds_gain):
        return "replay_sensitive_gain_confirmed"
    if replay_hit:
        return "replay_sensitive_eval_built_but_gain_weak"
    return "replay_sensitive_eval_not_ready"


def run_replay_sensitive_evidence(
    *,
    baseline_gate_path: str = str(DEFAULT_BASELINE_GATE),
    admitted_taskset_path: str = str(DEFAULT_ADMITTED_TASKSET),
    experience_store_path: str = str(DEFAULT_EXPERIENCE_STORE),
    results_out_dir: str = str(DEFAULT_RESULTS_DIR),
    out_dir: str = str(DEFAULT_OUT_DIR),
    timeout_sec: int = 600,
) -> dict:
    baseline_gate = _load_json(baseline_gate_path)
    admitted_taskset = _load_json(admitted_taskset_path)
    task_count = int(admitted_taskset.get("task_count") or 0)
    if task_count <= 0 or str(baseline_gate.get("decision") or "") != "replay_sensitive_eval_ready":
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": _now_utc(),
            "status": "PASS",
            "baseline_gate_path": str(Path(baseline_gate_path).resolve()) if Path(baseline_gate_path).exists() else str(baseline_gate_path),
            "admitted_taskset_path": str(Path(admitted_taskset_path).resolve()) if Path(admitted_taskset_path).exists() else str(admitted_taskset_path),
            "experience_store_path": str(Path(experience_store_path).resolve()) if Path(experience_store_path).exists() else str(experience_store_path),
            "baseline": baseline_gate.get("admitted_baseline") or {},
            "retrieval_summary": baseline_gate.get("retrieval_summary") or {},
            "replay": {},
            "delta": _metric_delta(baseline_gate.get("admitted_baseline") or {}, {}),
            "version_decision": "replay_sensitive_eval_not_ready",
        }
        out_root = Path(out_dir)
        _write_json(out_root / "summary.json", summary)
        _write_text(
            out_root / "summary.md",
            "\n".join(
                [
                    "# v0.3.15 Replay Evidence",
                    "",
                    "- version_decision: `replay_sensitive_eval_not_ready`",
                    "- note: `no admitted replay-sensitive eval slice was available for replay rerun`",
                    "",
                ]
            ),
        )
        return summary
    replay = run_authority_eval(
        taskset_path=admitted_taskset_path,
        results_out_dir=results_out_dir,
        out_dir=str(Path(out_dir) / "replay"),
        evaluation_label="v0315_replay",
        experience_source=str(Path(experience_store_path).resolve()) if Path(experience_store_path).exists() else str(experience_store_path),
        experience_replay="on",
        planner_experience_injection="on",
        planner_experience_max_tokens=400,
        timeout_sec=timeout_sec,
    )
    decision = _decide(baseline_gate, replay)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "baseline_gate_path": str(Path(baseline_gate_path).resolve()) if Path(baseline_gate_path).exists() else str(baseline_gate_path),
        "admitted_taskset_path": str(Path(admitted_taskset_path).resolve()) if Path(admitted_taskset_path).exists() else str(admitted_taskset_path),
        "experience_store_path": str(Path(experience_store_path).resolve()) if Path(experience_store_path).exists() else str(experience_store_path),
        "baseline": baseline_gate.get("admitted_baseline") or {},
        "retrieval_summary": baseline_gate.get("retrieval_summary") or {},
        "replay": replay,
        "delta": _metric_delta(baseline_gate.get("admitted_baseline") or {}, replay),
        "version_decision": decision,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", summary)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.15 Replay Evidence",
                "",
                f"- version_decision: `{decision}`",
                f"- success_rate_pct_delta: `{summary['delta']['success_rate_pct_delta']}`",
                f"- progressive_solve_rate_pct_delta: `{summary['delta']['progressive_solve_rate_pct_delta']}`",
                f"- replay_hit_rate_pct: `{replay.get('replay_hit_rate_pct')}`",
                "",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.3.15 replay evidence on the replay-sensitive eval slice.")
    parser.add_argument("--baseline-gate", default=str(DEFAULT_BASELINE_GATE))
    parser.add_argument("--admitted-taskset", default=str(DEFAULT_ADMITTED_TASKSET))
    parser.add_argument("--experience-store", default=str(DEFAULT_EXPERIENCE_STORE))
    parser.add_argument("--results-out-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = run_replay_sensitive_evidence(
        baseline_gate_path=str(args.baseline_gate),
        admitted_taskset_path=str(args.admitted_taskset),
        experience_store_path=str(args.experience_store),
        results_out_dir=str(args.results_out_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": payload.get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
