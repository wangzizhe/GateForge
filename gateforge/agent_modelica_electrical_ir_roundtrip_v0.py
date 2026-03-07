from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_modeling_ir_v0 import compare_ir_roundtrip, ir_to_modelica, modelica_to_ir, validate_ir


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Electrical IR Roundtrip v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- pass_count: `{payload.get('pass_count')}`",
        f"- pass_rate_pct: `{payload.get('pass_rate_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((float(part) / float(total)) * 100.0, 2)


def _select_tasks(all_tasks: list[dict], task_ids: list[str], max_tasks: int) -> list[dict]:
    normalized_ids = {str(x).strip() for x in (task_ids or []) if str(x).strip()}
    selected: list[dict] = []
    for task in all_tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id") or "").strip()
        if not task_id:
            continue
        if normalized_ids and task_id not in normalized_ids:
            continue
        selected.append(task)
    if max_tasks > 0:
        return selected[:max_tasks]
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Roundtrip-check modeling_ir_v0 tasks for electrical domain")
    parser.add_argument("--benchmark", default="benchmarks/agent_modelica_electrical_tasks_v0.json")
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--modelica-dir", default="artifacts/agent_modelica_electrical_ir_roundtrip_v0/modelica")
    parser.add_argument("--records-out", default="artifacts/agent_modelica_electrical_ir_roundtrip_v0/records.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_electrical_ir_roundtrip_v0/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    benchmark = _load_json(args.benchmark)
    tasks = benchmark.get("tasks") if isinstance(benchmark.get("tasks"), list) else []
    whitelist = [str(x) for x in (benchmark.get("component_whitelist") or []) if str(x).strip()]
    selected = _select_tasks(tasks, args.task_id, int(args.max_tasks))
    if not selected:
        print(json.dumps({"status": "FAIL", "reason": "taskset_empty"}))
        raise SystemExit(1)

    records: list[dict] = []
    pass_count = 0
    for task in selected:
        task_id = str(task.get("task_id") or "")
        scale = str(task.get("scale") or "")
        ir = task.get("ir") if isinstance(task.get("ir"), dict) else {}

        valid, errors = validate_ir(ir, allowed_component_types=whitelist)
        record = {
            "task_id": task_id,
            "scale": scale,
            "valid_ir": valid,
            "validation_errors": errors,
            "roundtrip_match": False,
            "diff_keys": [],
            "modelica_path": "",
        }
        if valid:
            modelica_text = ir_to_modelica(ir, allowed_component_types=whitelist)
            modelica_path = str(Path(args.modelica_dir) / f"{task_id}.mo")
            _write_text(modelica_path, modelica_text)
            parsed = modelica_to_ir(modelica_text)
            cmp = compare_ir_roundtrip(ir, parsed, ignore_source_meta=True)
            record["roundtrip_match"] = bool(cmp.get("match"))
            record["diff_keys"] = [str(x) for x in (cmp.get("diff_keys") or [])]
            record["modelica_path"] = modelica_path

        if record["valid_ir"] and record["roundtrip_match"]:
            pass_count += 1
        records.append(record)

    status = "PASS" if pass_count == len(records) else "FAIL"
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "benchmark_path": args.benchmark,
        "total_tasks": len(records),
        "pass_count": pass_count,
        "pass_rate_pct": _ratio(pass_count, len(records)),
        "records_out": args.records_out,
        "modelica_dir": args.modelica_dir,
    }
    payload = {
        "schema_version": "agent_modelica_electrical_ir_roundtrip_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "records": records,
    }
    _write_json(args.records_out, payload)
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)

    print(json.dumps({"status": status, "total_tasks": len(records), "pass_count": pass_count}))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
