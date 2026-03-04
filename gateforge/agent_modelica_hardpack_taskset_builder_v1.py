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
        "# GateForge Agent Modelica Hardpack Taskset Builder v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- task_count: `{payload.get('task_count')}`",
        f"- hardpack_version: `{payload.get('hardpack_version')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _default_baseline_metrics() -> dict:
    return {
        "steady_state_error": 0.01,
        "overshoot": 0.05,
        "settling_time": 1.0,
        "runtime_seconds": 1.0,
        "events": 10,
    }


def _default_candidate_metrics(ftype: str, baseline: dict) -> dict:
    out = dict(baseline)
    if ftype == "semantic_regression":
        out["steady_state_error"] = 0.03
    elif ftype == "simulate_error":
        out["events"] = 8
    elif ftype == "model_check_error":
        out["runtime_seconds"] = 1.2
    return out


def _to_task(case: dict) -> dict:
    mutation_id = str(case.get("mutation_id") or "").strip()
    ftype = str(case.get("expected_failure_type") or "unknown").strip().lower()
    baseline = _default_baseline_metrics()
    return {
        "task_id": f"task_{mutation_id}",
        "scale": str(case.get("target_scale") or "unknown").strip().lower(),
        "failure_type": ftype,
        "mutation_id": mutation_id,
        "source_model_path": str(case.get("source_model_path") or ""),
        "mutated_model_path": str(case.get("mutated_model_path") or ""),
        "repro_command": str(case.get("repro_command") or ""),
        "expected_stage": str(case.get("expected_stage") or "unknown"),
        "mock_success_round": 2,
        "mock_round_duration_sec": 30,
        "baseline_metrics": baseline,
        "candidate_metrics": _default_candidate_metrics(ftype=ftype, baseline=baseline),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build agent modelica taskset directly from locked hardpack")
    parser.add_argument("--hardpack", required=True)
    parser.add_argument("--taskset-out", default="artifacts/agent_modelica_hardpack_taskset_builder_v1/taskset.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_hardpack_taskset_builder_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    hardpack = _load_json(args.hardpack)
    cases = hardpack.get("cases") if isinstance(hardpack.get("cases"), list) else []
    cases = [x for x in cases if isinstance(x, dict)]
    tasks = [_to_task(case) for case in cases]

    taskset = {
        "schema_version": "agent_modelica_taskset_v1",
        "snapshot_version": str(hardpack.get("hardpack_version") or "hardpack_unknown"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tasks": tasks,
        "sources": {"hardpack": args.hardpack},
    }
    _write_json(args.taskset_out, taskset)

    summary = {
        "schema_version": "agent_modelica_hardpack_taskset_builder_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if tasks else "NEEDS_REVIEW",
        "hardpack_version": str(hardpack.get("hardpack_version") or "unknown"),
        "task_count": len(tasks),
        "taskset_out": args.taskset_out,
        "sources": {"hardpack": args.hardpack},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": summary.get("status"), "task_count": summary.get("task_count")}))


if __name__ == "__main__":
    main()
