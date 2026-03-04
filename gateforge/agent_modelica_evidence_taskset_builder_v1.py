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
        "# GateForge Agent Modelica Evidence Taskset Builder v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- included_scales: `{','.join(payload.get('included_scales') or [])}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _build_baseline_metrics(scale: str) -> dict:
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


def _build_candidate_metrics(failure_type: str, baseline: dict) -> dict:
    candidate = dict(baseline)
    if failure_type == "model_check_error":
        candidate["runtime_seconds"] = float(baseline.get("runtime_seconds", 2.0)) + 0.2
    elif failure_type == "simulate_error":
        candidate["events"] = max(0, int(baseline.get("events", 10)) - 2)
        candidate["settling_time"] = float(baseline.get("settling_time", 1.0)) + 0.3
    elif failure_type == "semantic_regression":
        candidate["steady_state_error"] = float(baseline.get("steady_state_error", 0.01)) + 0.01
    return candidate


def _make_evidence(metrics: dict, check_ok: bool, simulate_ok: bool) -> dict:
    return {
        "status": "success" if check_ok and simulate_ok else "failed",
        "gate": "PASS" if check_ok and simulate_ok else "FAIL",
        "check_ok": check_ok,
        "simulate_ok": simulate_ok,
        "metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build evidence-mode taskset from existing taskset")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--include-scales", default="medium,large")
    parser.add_argument("--per-scale-limit", type=int, default=20)
    parser.add_argument("--taskset-out", default="artifacts/agent_modelica_evidence_taskset_builder_v1/taskset.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_evidence_taskset_builder_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    include_scales = [x.strip().lower() for x in str(args.include_scales).split(",") if x.strip()]
    if not include_scales:
        include_scales = ["medium", "large"]

    source = _load_json(args.taskset)
    tasks = source.get("tasks") if isinstance(source.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]

    out_tasks: list[dict] = []
    counts_by_scale = {s: 0 for s in include_scales}
    limit = max(1, int(args.per_scale_limit))
    for task in tasks:
        scale = str(task.get("scale") or "").lower()
        if scale not in counts_by_scale:
            continue
        if counts_by_scale[scale] >= limit:
            continue
        failure_type = str(task.get("failure_type") or "unknown")
        baseline_metrics = _build_baseline_metrics(scale)
        candidate_metrics = _build_candidate_metrics(failure_type=failure_type, baseline=baseline_metrics)
        baseline_evidence = _make_evidence(metrics=baseline_metrics, check_ok=True, simulate_ok=True)
        candidate_evidence = _make_evidence(metrics=candidate_metrics, check_ok=True, simulate_ok=True)
        out_tasks.append(
            {
                "task_id": task.get("task_id"),
                "mutation_id": task.get("mutation_id"),
                "scale": scale,
                "failure_type": failure_type,
                "expected_stage": task.get("expected_stage") or "simulate",
                "observed_repair_rounds": 2,
                "observed_elapsed_sec": int(round(float(candidate_metrics.get("runtime_seconds", 2.0)) * 20.0)),
                "baseline_evidence": baseline_evidence,
                "candidate_evidence": candidate_evidence,
                "physical_invariants": task.get("physical_invariants", []),
            }
        )
        counts_by_scale[scale] += 1

    status = "PASS" if out_tasks else "FAIL"
    taskset_payload = {
        "schema_version": "agent_modelica_taskset_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "evidence",
        "tasks": out_tasks,
    }
    _write_json(args.taskset_out, taskset_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": len(out_tasks),
        "included_scales": include_scales,
        "counts_by_scale": counts_by_scale,
        "taskset_out": args.taskset_out,
        "sources": {"taskset": args.taskset},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "total_tasks": len(out_tasks)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
