from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_electrical_msl_semantics_v0 import (
    IR_PARAM_ALIAS_TO_CANONICAL_BY_COMPONENT_TYPE,
    IR_PARAM_KEYS_BY_COMPONENT_TYPE,
    IR_TO_MODELICA_PARAM_BY_COMPONENT_TYPE,
    MODELICA_TO_IR_PARAM_BY_COMPONENT_TYPE,
    PORT_SIGNATURES_BY_COMPONENT_TYPE,
)


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
    required = payload.get("required_fields") if isinstance(payload.get("required_fields"), list) else []
    lines = [
        "# Agent Modelica L2 Contract Snapshot v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- benchmark_path: `{payload.get('benchmark_path')}`",
        f"- sample_task_count: `{payload.get('sample_task_count')}`",
        "",
        "## Required Fields",
        "",
    ]
    for name in required:
        lines.append(f"- `{name}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _to_sorted_string_dict_list(payload: dict[str, set[str]] | dict[str, dict[str, str]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key in sorted(payload.keys()):
        value = payload[key]
        if isinstance(value, set):
            out[key] = sorted(value)
        elif isinstance(value, dict):
            out[key] = {k: value[k] for k in sorted(value.keys())}
        else:
            out[key] = value
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Export L2 contract snapshot for electrical modeling IR and OMC adapter")
    parser.add_argument("--benchmark", default="benchmarks/agent_modelica_electrical_tasks_v0.json")
    parser.add_argument("--sample-count", type=int, default=3)
    parser.add_argument("--sample-scales", default="small,medium")
    parser.add_argument("--out", default="assets_private/agent_modelica_l2_contract_snapshot_v0/contract_snapshot.json")
    parser.add_argument("--sample-out", default="assets_private/agent_modelica_l2_contract_snapshot_v0/sample_ir_tasks.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    benchmark = _load_json(args.benchmark)
    tasks = benchmark.get("tasks") if isinstance(benchmark.get("tasks"), list) else []
    scales = {str(x).strip().lower() for x in str(args.sample_scales).split(",") if str(x).strip()}
    selected = []
    for row in tasks:
        if not isinstance(row, dict):
            continue
        scale = str(row.get("scale") or "").lower()
        if scales and scale not in scales:
            continue
        selected.append(row)
    selected = selected[: max(1, int(args.sample_count))]

    required_fields = [
        "schema_version",
        "model_name",
        "components",
        "connections",
        "structural_balance.variable_count",
        "structural_balance.equation_count",
        "simulation.start_time",
        "simulation.stop_time",
        "simulation.number_of_intervals",
        "simulation.tolerance",
        "simulation.method",
        "validation_targets",
    ]

    out = {
        "schema_version": "agent_modelica_l2_contract_snapshot_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "benchmark_path": args.benchmark,
        "required_fields": required_fields,
        "component_whitelist": sorted([str(x) for x in (benchmark.get("component_whitelist") or []) if str(x).strip()]),
        "ir_param_keys_by_component_type": _to_sorted_string_dict_list(IR_PARAM_KEYS_BY_COMPONENT_TYPE),
        "ir_param_alias_to_canonical_by_component_type": _to_sorted_string_dict_list(
            IR_PARAM_ALIAS_TO_CANONICAL_BY_COMPONENT_TYPE
        ),
        "ir_to_modelica_param_by_component_type": _to_sorted_string_dict_list(IR_TO_MODELICA_PARAM_BY_COMPONENT_TYPE),
        "modelica_to_ir_param_by_component_type": _to_sorted_string_dict_list(MODELICA_TO_IR_PARAM_BY_COMPONENT_TYPE),
        "port_signatures_by_component_type": _to_sorted_string_dict_list(PORT_SIGNATURES_BY_COMPONENT_TYPE),
        "sample_task_count": len(selected),
        "sample_task_ids": [str(x.get("task_id") or "") for x in selected if isinstance(x, dict)],
    }

    _write_json(args.out, out)
    _write_json(args.sample_out, {"tasks": selected})
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    print(json.dumps({"status": "PASS", "sample_task_count": len(selected)}))


if __name__ == "__main__":
    main()
