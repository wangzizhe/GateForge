from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Strategy A/B v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- delta_success_at_k_pct: `{(payload.get('delta') or {}).get('success_at_k_pct')}`",
        f"- delta_median_time_to_pass_sec: `{(payload.get('delta') or {}).get('median_time_to_pass_sec')}`",
        f"- delta_median_repair_rounds: `{(payload.get('delta') or {}).get('median_repair_rounds')}`",
        f"- delta_regression_count: `{(payload.get('delta') or {}).get('regression_count')}`",
        f"- delta_physics_fail_count: `{(payload.get('delta') or {}).get('physics_fail_count')}`",
        f"- strategy_signal_delta_score: `{(payload.get('strategy_signal') or {}).get('delta_score')}`",
        f"- strategy_signal_triggered: `{(payload.get('strategy_signal') or {}).get('triggered')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _build_control_playbook(path: str) -> str:
    payload = {
        "schema_version": "agent_modelica_repair_playbook_v1",
        "status": "PASS",
        "playbook": [
            {
                "failure_type": ftype,
                "strategy_id": f"control_generic_{ftype}",
                "name": "Control Generic Repair",
                "priority": 1,
                "actions": ["classify failure and apply conservative generic fix"],
                "preferred_stage": "unknown",
            }
            for ftype in ("model_check_error", "simulate_error", "semantic_regression")
        ],
    }
    _write_json(path, payload)
    return path


def _run_contract(taskset: str, out_dir: Path, playbook: str, mode: str, runtime_threshold: float) -> tuple[dict, dict]:
    results = out_dir / "results.json"
    summary = out_dir / "summary.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "gateforge.agent_modelica_run_contract_v1",
            "--taskset",
            taskset,
            "--mode",
            mode,
            "--runtime-threshold",
            str(float(runtime_threshold)),
            "--repair-playbook",
            playbook,
            "--results-out",
            str(results),
            "--out",
            str(summary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout)
    return _load_json(str(summary)), _load_json(str(results))


def _delta(treatment: dict, control: dict, key: str) -> float | None:
    tv = treatment.get(key)
    cv = control.get(key)
    if not isinstance(tv, (int, float)) or not isinstance(cv, (int, float)):
        return None
    return round(float(tv) - float(cv), 2)


def _build_per_failure_delta(control_results: dict, treatment_results: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    c_recs = control_results.get("records") if isinstance(control_results.get("records"), list) else []
    t_recs = treatment_results.get("records") if isinstance(treatment_results.get("records"), list) else []
    c_map = {str(x.get("task_id") or ""): x for x in c_recs if isinstance(x, dict)}
    t_map = {str(x.get("task_id") or ""): x for x in t_recs if isinstance(x, dict)}
    keys = sorted(set(c_map.keys()) & set(t_map.keys()))
    by_failure: dict[str, list[tuple[bool, bool, float, float]]] = {}
    for k in keys:
        c = c_map[k]
        t = t_map[k]
        ftype = str(t.get("failure_type") or c.get("failure_type") or "unknown")
        row = (
            bool(c.get("passed")),
            bool(t.get("passed")),
            float(c.get("elapsed_sec") or 0.0),
            float(t.get("elapsed_sec") or 0.0),
        )
        by_failure.setdefault(ftype, []).append(row)

    for ftype, rows in by_failure.items():
        n = len(rows)
        control_pass = len([x for x in rows if x[0]])
        treatment_pass = len([x for x in rows if x[1]])
        control_avg_time = round(sum(x[2] for x in rows) / n, 2) if n else None
        treatment_avg_time = round(sum(x[3] for x in rows) / n, 2) if n else None
        out[ftype] = {
            "count": n,
            "control_pass_rate_pct": round((control_pass / n) * 100.0, 2) if n else 0.0,
            "treatment_pass_rate_pct": round((treatment_pass / n) * 100.0, 2) if n else 0.0,
            "delta_pass_rate_pct": round(((treatment_pass - control_pass) / n) * 100.0, 2) if n else 0.0,
            "control_avg_elapsed_sec": control_avg_time,
            "treatment_avg_elapsed_sec": treatment_avg_time,
            "delta_avg_elapsed_sec": (
                round((treatment_avg_time - control_avg_time), 2)
                if isinstance(control_avg_time, (int, float)) and isinstance(treatment_avg_time, (int, float))
                else None
            ),
        }
    return out


def _strategy_signal(results: dict) -> dict[str, float]:
    records = results.get("records") if isinstance(results.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    total = len(records)
    if total <= 0:
        return {
            "task_count": 0.0,
            "stage_match_rate_pct": 0.0,
            "failure_match_rate_pct": 0.0,
            "avg_strategy_confidence": 0.0,
            "avg_planned_actions": 0.0,
            "score": 0.0,
        }

    stage_matched = 0
    failure_matched = 0
    confidence_sum = 0.0
    action_count_sum = 0
    for rec in records:
        audit = rec.get("repair_audit") if isinstance(rec.get("repair_audit"), dict) else {}
        reason = str(audit.get("strategy_reason") or "")
        if reason == "stage_matched":
            stage_matched += 1
        if reason in {"stage_matched", "failure_type_matched"}:
            failure_matched += 1
        confidence_sum += float(audit.get("strategy_confidence", 0.0) or 0.0)
        actions = audit.get("actions_planned") if isinstance(audit.get("actions_planned"), list) else []
        action_count_sum += len([x for x in actions if isinstance(x, str)])

    stage_match_rate = stage_matched / total
    failure_match_rate = failure_matched / total
    avg_conf = confidence_sum / total
    avg_actions = action_count_sum / total

    # Evidence-mode signal focuses on strategy-task fit quality when hard outcomes are tied.
    score = (0.6 * stage_match_rate) + (0.2 * failure_match_rate) + (0.2 * min(1.0, max(0.0, avg_conf)))
    return {
        "task_count": float(total),
        "stage_match_rate_pct": round(stage_match_rate * 100.0, 2),
        "failure_match_rate_pct": round(failure_match_rate * 100.0, 2),
        "avg_strategy_confidence": round(avg_conf, 4),
        "avg_planned_actions": round(avg_actions, 2),
        "score": round(score, 4),
    }


def _strategy_signal_by_failure(results: dict) -> dict[str, dict[str, float]]:
    records = results.get("records") if isinstance(results.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]
    buckets: dict[str, list[dict]] = {}
    for rec in records:
        ftype = str(rec.get("failure_type") or "unknown")
        buckets.setdefault(ftype, []).append(rec)

    out: dict[str, dict[str, float]] = {}
    for ftype, rows in buckets.items():
        wrapped = {"records": rows}
        out[ftype] = _strategy_signal(wrapped)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B test repair playbook on same taskset")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--treatment-playbook", required=True)
    parser.add_argument("--mode", choices=["mock", "evidence"], default="mock")
    parser.add_argument("--runtime-threshold", type=float, default=0.2)
    parser.add_argument("--evidence-signal-threshold", type=float, default=0.08)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_strategy_ab_test_v1")
    parser.add_argument("--out", default="artifacts/agent_modelica_strategy_ab_test_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as d:
        control_playbook = _build_control_playbook(str(Path(d) / "control_playbook.json"))
        control_summary, control_results = _run_contract(
            taskset=args.taskset,
            out_dir=out_dir / "control",
            playbook=control_playbook,
            mode=args.mode,
            runtime_threshold=float(args.runtime_threshold),
        )
        treatment_summary, treatment_results = _run_contract(
            taskset=args.taskset,
            out_dir=out_dir / "treatment",
            playbook=args.treatment_playbook,
            mode=args.mode,
            runtime_threshold=float(args.runtime_threshold),
        )

    delta = {
        "success_at_k_pct": _delta(treatment_summary, control_summary, "success_at_k_pct"),
        "median_time_to_pass_sec": _delta(treatment_summary, control_summary, "median_time_to_pass_sec"),
        "median_repair_rounds": _delta(treatment_summary, control_summary, "median_repair_rounds"),
        "regression_count": _delta(treatment_summary, control_summary, "regression_count"),
        "physics_fail_count": _delta(treatment_summary, control_summary, "physics_fail_count"),
    }
    per_failure = _build_per_failure_delta(control_results=control_results, treatment_results=treatment_results)
    signal_control = _strategy_signal(control_results)
    signal_treatment = _strategy_signal(treatment_results)
    signal_delta = round(float(signal_treatment.get("score", 0.0)) - float(signal_control.get("score", 0.0)), 4)
    signal_control_by_failure = _strategy_signal_by_failure(control_results)
    signal_treatment_by_failure = _strategy_signal_by_failure(treatment_results)
    signal_delta_by_failure: dict[str, float] = {}
    all_failure_types = sorted(set(signal_control_by_failure.keys()) | set(signal_treatment_by_failure.keys()))
    for ftype in all_failure_types:
        c = float((signal_control_by_failure.get(ftype) or {}).get("score", 0.0) or 0.0)
        t = float((signal_treatment_by_failure.get(ftype) or {}).get("score", 0.0) or 0.0)
        signal_delta_by_failure[ftype] = round(t - c, 4)

    success_ok = isinstance(delta.get("success_at_k_pct"), (int, float)) and delta.get("success_at_k_pct", 0.0) >= 0.0
    safety_ok = (
        isinstance(delta.get("physics_fail_count"), (int, float))
        and delta.get("physics_fail_count", 0.0) <= 0.0
        and isinstance(delta.get("regression_count"), (int, float))
        and delta.get("regression_count", 0.0) <= 0.0
    )
    rounds_improved = isinstance(delta.get("median_repair_rounds"), (int, float)) and delta.get("median_repair_rounds", 0.0) < 0.0
    time_improved = isinstance(delta.get("median_time_to_pass_sec"), (int, float)) and delta.get("median_time_to_pass_sec", 0.0) < 0.0
    evidence_signal_promote = (
        args.mode == "evidence"
        and success_ok
        and safety_ok
        and not (rounds_improved or time_improved)
        and signal_delta >= float(args.evidence_signal_threshold)
    )
    decision = "PROMOTE_TREATMENT" if (success_ok and safety_ok and (rounds_improved or time_improved or evidence_signal_promote)) else "KEEP_CONTROL"

    payload = {
        "schema_version": "agent_modelica_strategy_ab_test_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "decision": decision,
        "mode": args.mode,
        "delta": delta,
        "strategy_signal": {
            "control": signal_control,
            "treatment": signal_treatment,
            "delta_score": signal_delta,
            "threshold": float(args.evidence_signal_threshold),
            "triggered": bool(evidence_signal_promote),
        },
        "strategy_signal_by_failure_type": {
            "control": signal_control_by_failure,
            "treatment": signal_treatment_by_failure,
            "delta_score": signal_delta_by_failure,
        },
        "per_failure_type": per_failure,
        "control": {
            "summary": control_summary,
            "results_path": str((out_dir / "control" / "results.json")),
        },
        "treatment": {
            "summary": treatment_summary,
            "results_path": str((out_dir / "treatment" / "results.json")),
            "playbook": args.treatment_playbook,
        },
        "sources": {
            "taskset": args.taskset,
            "treatment_playbook": args.treatment_playbook,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "decision": decision}))


if __name__ == "__main__":
    main()
