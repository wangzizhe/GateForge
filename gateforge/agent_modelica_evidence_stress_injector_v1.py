from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
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
        "# GateForge Agent Modelica Evidence Stress Injector v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- hard_fail_injected: `{payload.get('hard_fail_injected')}`",
        f"- slow_pass_injected: `{payload.get('slow_pass_injected')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _safe_metric(d: dict, key: str, fallback: float) -> float:
    try:
        return float(d.get(key, fallback) or fallback)
    except (TypeError, ValueError):
        return fallback


def _default_metrics(scale: str) -> dict:
    base = {
        "steady_state_error": 0.01,
        "overshoot": 0.04,
        "settling_time": 1.2,
        "runtime_seconds": 2.0,
        "events": 12,
    }
    if scale == "large":
        base.update({"settling_time": 2.5, "runtime_seconds": 4.0, "events": 20})
    elif scale == "medium":
        base.update({"settling_time": 1.8, "runtime_seconds": 3.0, "events": 15})
    return base


def _evidence(task: dict, key: str, scale: str) -> dict:
    row = task.get(key) if isinstance(task.get(key), dict) else {}
    if row:
        out = dict(row)
        metrics = out.get("metrics") if isinstance(out.get("metrics"), dict) else {}
        out["metrics"] = dict(metrics)
        return out
    return {
        "status": "success",
        "gate": "PASS",
        "check_ok": True,
        "simulate_ok": True,
        "metrics": _default_metrics(scale=scale),
    }


def _task_indices_round_robin(tasks: list[dict], limit: int, excluded: set[int]) -> list[int]:
    if limit <= 0:
        return []
    buckets: dict[tuple[str, str], list[int]] = {}
    for idx, task in enumerate(tasks):
        if idx in excluded:
            continue
        scale = str(task.get("scale") or "unknown")
        ftype = str(task.get("failure_type") or "unknown")
        buckets.setdefault((scale, ftype), []).append(idx)
    picked: list[int] = []
    while len(picked) < limit:
        progress = False
        for key in sorted(buckets.keys()):
            rows = buckets.get(key) or []
            if not rows:
                continue
            picked.append(rows.pop(0))
            progress = True
            if len(picked) >= limit:
                break
        if not progress:
            break
    return picked


def _inject_hard_fail(task: dict) -> dict:
    out = dict(task)
    scale = str(out.get("scale") or "unknown").lower()
    failure_type = str(out.get("failure_type") or "unknown").lower()
    base = _evidence(out, "baseline_evidence", scale=scale)
    cand = _evidence(out, "candidate_evidence", scale=scale)

    base_metrics = dict(base.get("metrics") or {})
    cand_metrics = dict(cand.get("metrics") or base_metrics)

    if failure_type == "model_check_error":
        cand.update({"status": "failed", "gate": "FAIL", "check_ok": False, "simulate_ok": False})
        out["_stress_reason"] = "hard_fail_model_check"
    elif failure_type == "simulate_error":
        cand.update({"status": "failed", "gate": "FAIL", "check_ok": True, "simulate_ok": False})
        out["_stress_reason"] = "hard_fail_simulate"
    else:
        # Keep check/sim pass, break at physics contract.
        cand.update({"status": "success", "gate": "PASS", "check_ok": True, "simulate_ok": True})
        cand_metrics["steady_state_error"] = max(0.2, _safe_metric(base_metrics, "steady_state_error", 0.01) * 8.0)
        invariants = out.get("physical_invariants") if isinstance(out.get("physical_invariants"), list) else []
        if not invariants:
            out["physical_invariants"] = [
                {"type": "range", "metric": "steady_state_error", "min": 0.0, "max": 0.05}
            ]
        out["_stress_reason"] = "hard_fail_physics_contract"

    cand["metrics"] = cand_metrics
    out["baseline_evidence"] = base
    out["candidate_evidence"] = cand
    out["observed_repair_rounds"] = max(3, int(out.get("observed_repair_rounds", 1) or 1))
    out["observed_elapsed_sec"] = int(out.get("observed_elapsed_sec", 30) or 30) + 90
    out["_stress_class"] = "hard_fail"
    return out


def _inject_slow_pass(task: dict) -> dict:
    out = dict(task)
    scale = str(out.get("scale") or "unknown").lower()
    base = _evidence(out, "baseline_evidence", scale=scale)
    cand = _evidence(out, "candidate_evidence", scale=scale)
    cand.update({"status": "success", "gate": "PASS", "check_ok": True, "simulate_ok": True})

    cand_metrics = dict(cand.get("metrics") or {})
    runtime = _safe_metric(cand_metrics, "runtime_seconds", _safe_metric(base.get("metrics") or {}, "runtime_seconds", 2.0))
    cand_metrics["runtime_seconds"] = round(runtime * 1.35, 3)
    cand["metrics"] = cand_metrics
    out["baseline_evidence"] = base
    out["candidate_evidence"] = cand

    bonus = 70 if scale == "large" else (50 if scale == "medium" else 30)
    out["observed_repair_rounds"] = max(2, int(out.get("observed_repair_rounds", 1) or 1))
    out["observed_elapsed_sec"] = int(out.get("observed_elapsed_sec", 30) or 30) + bonus
    out["_stress_class"] = "slow_pass"
    out["_stress_reason"] = "slow_pass_runtime_stress"
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject hard-fail and slow-pass stress rows into evidence taskset")
    parser.add_argument("--taskset-in", required=True)
    parser.add_argument("--hard-fail-count", type=int, default=0)
    parser.add_argument("--slow-pass-count", type=int, default=0)
    parser.add_argument("--out-taskset", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_evidence_stress_injector_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    src = _load_json(args.taskset_in)
    tasks = src.get("tasks") if isinstance(src.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]
    hard_target = max(0, int(args.hard_fail_count))
    slow_target = max(0, int(args.slow_pass_count))

    out_tasks = [dict(x) for x in tasks]
    used: set[int] = set()
    hard_indices = _task_indices_round_robin(out_tasks, hard_target, excluded=used)
    used.update(hard_indices)
    slow_indices = _task_indices_round_robin(out_tasks, slow_target, excluded=used)

    for idx in hard_indices:
        out_tasks[idx] = _inject_hard_fail(out_tasks[idx])
    for idx in slow_indices:
        out_tasks[idx] = _inject_slow_pass(out_tasks[idx])

    hard_injected = len(hard_indices)
    slow_injected = len(slow_indices)
    reasons: list[str] = []
    if hard_injected < hard_target:
        reasons.append("hard_fail_injection_shortfall")
    if slow_injected < slow_target:
        reasons.append("slow_pass_injection_shortfall")

    by_class = {"hard_fail": hard_injected, "slow_pass": slow_injected}
    by_failure_type: dict[str, int] = {}
    by_scale: dict[str, int] = {}
    for idx in [*hard_indices, *slow_indices]:
        row = out_tasks[idx]
        ftype = str(row.get("failure_type") or "unknown")
        scale = str(row.get("scale") or "unknown")
        by_failure_type[ftype] = int(by_failure_type.get(ftype, 0)) + 1
        by_scale[scale] = int(by_scale.get(scale, 0)) + 1

    out_taskset = {
        "schema_version": str(src.get("schema_version") or "agent_modelica_taskset_v1"),
        "snapshot_version": str(src.get("snapshot_version") or "unknown"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": str(src.get("mode") or "evidence"),
        "tasks": out_tasks,
        "sources": {"taskset_in": args.taskset_in},
    }
    _write_json(args.out_taskset, out_taskset)

    status = "PASS" if not reasons else "NEEDS_REVIEW"
    payload = {
        "schema_version": "agent_modelica_evidence_stress_injector_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": len(out_tasks),
        "hard_fail_target": hard_target,
        "hard_fail_injected": hard_injected,
        "slow_pass_target": slow_target,
        "slow_pass_injected": slow_injected,
        "injected_by_class": by_class,
        "injected_by_failure_type": by_failure_type,
        "injected_by_scale": by_scale,
        "out_taskset": args.out_taskset,
        "reasons": reasons,
        "sources": {"taskset_in": args.taskset_in},
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "hard_fail_injected": hard_injected,
                "slow_pass_injected": slow_injected,
            }
        )
    )


if __name__ == "__main__":
    main()
