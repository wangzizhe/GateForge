from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_modeling_ir_v0 import ir_to_modelica, validate_ir


DEFAULT_FAILURE_CYCLE = ("model_check_error", "simulate_error", "semantic_regression")
FAILURE_METADATA = {
    "model_check_error": {
        "expected_stage": "check",
        "category": "legacy_structural",
        "mutation_operator_family": "legacy_injection",
    },
    "simulate_error": {
        "expected_stage": "simulate",
        "category": "legacy_runtime",
        "mutation_operator_family": "legacy_injection",
    },
    "semantic_regression": {
        "expected_stage": "simulate",
        "category": "regression",
        "mutation_operator_family": "legacy_semantic",
    },
    "underconstrained_system": {
        "expected_stage": "check",
        "category": "topology_wiring",
        "mutation_operator_family": "topology_realism",
    },
    "connector_mismatch": {
        "expected_stage": "check",
        "category": "topology_wiring",
        "mutation_operator_family": "topology_realism",
    },
    "initialization_infeasible": {
        "expected_stage": "simulate",
        "category": "initialization",
        "mutation_operator_family": "initialization_realism",
    },
}
TOPOLOGY_MUTATION_OPERATOR_BY_FAILURE = {
    "model_check_error": "connector_port_typo",
    "simulate_error": "connection_drop_with_runtime_assert",
    "semantic_regression": "connection_polarity_flip",
}


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
        "# GateForge Agent Modelica Electrical Mutant Taskset v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        "",
    ]
    rows = payload.get("counts_by_failure_type") if isinstance(payload.get("counts_by_failure_type"), dict) else {}
    lines.append("## Counts By Failure Type")
    lines.append("")
    if rows:
        for key in sorted(rows.keys()):
            lines.append(f"- `{key}`: `{rows[key]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _insert_equation_line(model_text: str, line_to_insert: str) -> str:
    lines = str(model_text or "").splitlines()
    if not lines:
        return str(model_text or "")
    for idx, line in enumerate(lines):
        if re.match(r"^\s*equation\s*$", line):
            lines.insert(idx + 1, line_to_insert)
            return "\n".join(lines) + "\n"
    end_idx = -1
    for idx, line in enumerate(lines):
        if re.match(r"^\s*end\s+[A-Za-z_][A-Za-z0-9_]*\s*;\s*$", line):
            end_idx = idx
            break
    if end_idx < 0:
        return str(model_text or "")
    lines.insert(end_idx, "equation")
    lines.insert(end_idx + 1, line_to_insert)
    return "\n".join(lines) + "\n"


def _insert_initial_equation_lines(model_text: str, lines_to_insert: list[str]) -> str:
    lines = str(model_text or "").splitlines()
    if not lines or not lines_to_insert:
        return str(model_text or "")
    initial_block = [line for line in lines_to_insert if str(line).strip()]
    if not initial_block:
        return str(model_text or "")
    for idx, line in enumerate(lines):
        if re.match(r"^\s*initial\s+equation\s*$", line):
            insert_at = idx + 1
            for extra in reversed(initial_block):
                lines.insert(insert_at, extra)
            return "\n".join(lines) + "\n"
    for idx, line in enumerate(lines):
        if re.match(r"^\s*equation\s*$", line):
            lines.insert(idx, "initial equation")
            for offset, extra in enumerate(initial_block, start=1):
                lines.insert(idx + offset, extra)
            return "\n".join(lines) + "\n"
    end_idx = -1
    for idx, line in enumerate(lines):
        if re.match(r"^\s*end\s+[A-Za-z_][A-Za-z0-9_]*\s*;\s*$", line):
            end_idx = idx
            break
    if end_idx < 0:
        return str(model_text or "")
    lines.insert(end_idx, "initial equation")
    for offset, extra in enumerate(initial_block, start=1):
        lines.insert(end_idx + offset, extra)
    return "\n".join(lines) + "\n"


def _inject_model_check_error(model_text: str, token: str) -> str:
    return _insert_equation_line(model_text, f"  __gf_undef_{token} = 1.0;")


def _inject_simulate_error(model_text: str, token: str) -> str:
    return _insert_equation_line(model_text, f'  assert(false, "gateforge_simulate_error_{token}");')


def _flip_first_numeric_param(model_text: str) -> tuple[str, bool]:
    # Prefer source voltage sign inversion.
    patterns = [
        re.compile(
            r"(Modelica\.Electrical\.Analog\.Sources\.(?:ConstantVoltage|StepVoltage|SineVoltage)\s+[A-Za-z_][A-Za-z0-9_]*\([^;\n]*?\bV=)(-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)([^;\n]*\);)"
        ),
        re.compile(
            r"(Modelica\.Electrical\.Analog\.Basic\.Resistor\s+[A-Za-z_][A-Za-z0-9_]*\([^;\n]*?\bR=)(-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)([^;\n]*\);)"
        ),
    ]
    text = str(model_text or "")
    for pattern in patterns:
        m = pattern.search(text)
        if not m:
            continue
        raw = str(m.group(2))
        try:
            value = float(raw)
        except Exception:
            continue
        replacement = -value if value != 0.0 else 1.0
        patched = text[: m.start(2)] + str(replacement) + text[m.end(2) :]
        return patched, True
    return text, False


def _inject_semantic_regression(model_text: str, token: str) -> str:
    patched, ok = _flip_first_numeric_param(model_text)
    if ok:
        return patched
    return _insert_equation_line(model_text, f"  0 = 0; // gateforge_semantic_regression_{token}")


def _replace_connection_endpoint(model_text: str, source: str, target: str) -> tuple[str, bool]:
    line_re = re.compile(rf"connect\(\s*{re.escape(source)}\s*,\s*{re.escape(target)}\s*\)\s*;")
    m = line_re.search(model_text)
    if not m:
        return model_text, False
    before = model_text[: m.start()]
    after = model_text[m.end() :]
    replacement = f"connect({source}, {target});"
    return before + replacement + after, True


def _mutate_connector_port_typo(model_text: str, ir: dict) -> tuple[str, list[dict]]:
    connections = ir.get("connections") if isinstance(ir.get("connections"), list) else []
    if not connections:
        return model_text, []
    row = connections[0] if isinstance(connections[0], dict) else {}
    src = str(row.get("from") or "")
    dst = str(row.get("to") or "")
    if "." not in dst:
        return model_text, []
    comp, _port = dst.split(".", 1)
    new_dst = f"{comp}.badPort"
    # Replace text conservatively using exact old connect line.
    line_re = re.compile(rf"connect\(\s*{re.escape(src)}\s*,\s*{re.escape(dst)}\s*\)\s*;")
    m = line_re.search(model_text)
    if not m:
        return model_text, []
    replacement = f"connect({src}, {new_dst});"
    patched = model_text[: m.start()] + replacement + model_text[m.end() :]
    objects = [
        {
            "kind": "connection_endpoint",
            "from": src,
            "to_before": dst,
            "to_after": new_dst,
        }
    ]
    return patched, objects


def _mutate_connection_polarity_flip(model_text: str, ir: dict) -> tuple[str, list[dict]]:
    connections = ir.get("connections") if isinstance(ir.get("connections"), list) else []
    for row in connections:
        if not isinstance(row, dict):
            continue
        src = str(row.get("from") or "")
        dst = str(row.get("to") or "")
        if src.endswith(".p"):
            new_src = src[:-2] + ".n"
            line_re = re.compile(rf"connect\(\s*{re.escape(src)}\s*,\s*{re.escape(dst)}\s*\)\s*;")
            m = line_re.search(model_text)
            if not m:
                continue
            replacement = f"connect({new_src}, {dst});"
            patched = model_text[: m.start()] + replacement + model_text[m.end() :]
            objects = [
                {
                    "kind": "connection_endpoint",
                    "from_before": src,
                    "from_after": new_src,
                    "to": dst,
                }
            ]
            return patched, objects
    return model_text, []


def _mutate_connection_drop(model_text: str, ir: dict) -> tuple[str, list[dict]]:
    connections = ir.get("connections") if isinstance(ir.get("connections"), list) else []
    if not connections:
        return model_text, []
    row = connections[0] if isinstance(connections[0], dict) else {}
    src = str(row.get("from") or "")
    dst = str(row.get("to") or "")
    line_re = re.compile(rf"^\s*connect\(\s*{re.escape(src)}\s*,\s*{re.escape(dst)}\s*\)\s*;\s*$", flags=re.MULTILINE)
    m = line_re.search(model_text)
    if not m:
        return model_text, []
    patched = model_text[: m.start()] + model_text[m.end() :]
    objects = [{"kind": "connection_edge", "removed_from": src, "removed_to": dst}]
    return patched, objects


def _mutate_underconstrained_system(model_text: str, ir: dict) -> tuple[str, list[dict]]:
    patched, objects = _mutate_connection_drop(model_text=model_text, ir=ir)
    if not objects:
        return model_text, []
    enriched = []
    for row in objects:
        enriched.append(
            {
                **row,
                "kind": "connection_edge",
                "effect": "dangling_connectivity",
            }
        )
    return patched, enriched


def _pick_initialization_target(ir: dict) -> str:
    components = ir.get("components") if isinstance(ir.get("components"), list) else []
    preferred = [
        ("Modelica.Electrical.Analog.Basic.Resistor", "i"),
        ("Modelica.Electrical.Analog.Basic.Capacitor", "v"),
        ("Modelica.Electrical.Analog.Basic.Inductor", "i"),
        ("Modelica.Electrical.Analog.Sensors.VoltageSensor", "v"),
    ]
    for type_name, suffix in preferred:
        for row in components:
            if not isinstance(row, dict):
                continue
            if str(row.get("type") or "").strip() != type_name:
                continue
            comp_id = str(row.get("id") or "").strip()
            if comp_id:
                return f"{comp_id}.{suffix}"
    validation_targets = ir.get("validation_targets") if isinstance(ir.get("validation_targets"), list) else []
    for target in validation_targets:
        text = str(target or "").strip()
        if "." in text:
            return text
    return ""


def _mutate_initialization_infeasible(model_text: str, ir: dict) -> tuple[str, list[dict]]:
    target = _pick_initialization_target(ir)
    patched = _insert_initial_equation_lines(
        model_text,
        [
            f'  assert(false, "gateforge_initialization_infeasible_{hashlib.sha256(str(target or "init").encode("utf-8")).hexdigest()[:8]}");',
        ],
    )
    if patched == model_text:
        return model_text, []
    return patched, [
        {
            "kind": "initialization_trigger",
            "target": target or "initial_equation",
            "effect": "forced_initialization_failure",
        }
    ]


def _failure_meta(failure_type: str) -> dict:
    ftype = str(failure_type or "").strip().lower()
    return FAILURE_METADATA.get(
        ftype,
        {
            "expected_stage": "simulate",
            "category": "unknown",
            "mutation_operator_family": "unknown",
        },
    )


def _inject_failure(model_text: str, ir: dict, failure_type: str, token: str, mutation_style: str) -> tuple[str, str, list[dict]]:
    ftype = str(failure_type or "").strip().lower()
    style = str(mutation_style or "hybrid").strip().lower()
    if ftype == "underconstrained_system":
        patched, objects = _mutate_underconstrained_system(model_text=model_text, ir=ir)
        if objects:
            return patched, "drop_connect_equation", objects
        return model_text, "none", []
    if ftype == "connector_mismatch":
        patched, objects = _mutate_connector_port_typo(model_text=model_text, ir=ir)
        if objects:
            return patched, "connector_port_typo", objects
        return model_text, "none", []
    if ftype == "initialization_infeasible":
        patched, objects = _mutate_initialization_infeasible(model_text=model_text, ir=ir)
        if objects:
            return patched, "initial_equation_assert", objects
        return model_text, "none", []
    if style == "topology" and ftype in TOPOLOGY_MUTATION_OPERATOR_BY_FAILURE:
        op = TOPOLOGY_MUTATION_OPERATOR_BY_FAILURE.get(ftype) or ""
        if op == "connector_port_typo":
            patched, objects = _mutate_connector_port_typo(model_text=model_text, ir=ir)
            if objects:
                return patched, op, objects
        elif op == "connection_polarity_flip":
            patched, objects = _mutate_connection_polarity_flip(model_text=model_text, ir=ir)
            if objects:
                return patched, op, objects
        elif op == "connection_drop_with_runtime_assert":
            patched, objects = _mutate_connection_drop(model_text=model_text, ir=ir)
            patched = _insert_equation_line(patched, f'  assert(false, "gateforge_simulate_error_{token}");')
            return patched, op, objects
    if ftype == "model_check_error":
        return _inject_model_check_error(model_text, token), "undefined_symbol_injection", []
    if ftype == "simulate_error":
        return _inject_simulate_error(model_text, token), "runtime_assert_injection", []
    if ftype == "semantic_regression":
        return _inject_semantic_regression(model_text, token), "parameter_sign_flip", []
    return model_text, "none", []


def _task_selection(all_tasks: list[dict], scales: list[str], max_tasks: int) -> list[dict]:
    allowed_scales = {str(x).strip().lower() for x in scales if str(x).strip()}
    rows: list[dict] = []
    for row in all_tasks:
        if not isinstance(row, dict):
            continue
        scale = str(row.get("scale") or "").strip().lower()
        if allowed_scales and scale not in allowed_scales:
            continue
        task_id = str(row.get("task_id") or "").strip()
        ir = row.get("ir") if isinstance(row.get("ir"), dict) else {}
        if not task_id or not ir:
            continue
        rows.append(row)
    rows = sorted(rows, key=lambda x: (str(x.get("scale") or ""), str(x.get("task_id") or "")))
    if max_tasks > 0:
        return rows[:max_tasks]
    return rows


def _token_for(task_id: str, failure_type: str) -> str:
    raw = f"{task_id}:{failure_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build electrical mutant taskset from modeling_ir_v0 benchmark tasks")
    parser.add_argument("--benchmark", default="benchmarks/agent_modelica_electrical_tasks_v0.json")
    parser.add_argument("--scales", default="small,medium,large")
    parser.add_argument("--failure-cycle", default="model_check_error,simulate_error,semantic_regression")
    parser.add_argument("--failure-types", default="")
    parser.add_argument("--mutation-style", choices=["hybrid", "topology"], default="hybrid")
    parser.add_argument("--expand-failure-types", action="store_true")
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--source-models-dir", default="artifacts/agent_modelica_electrical_mutant_taskset_v0/source_models")
    parser.add_argument("--mutants-dir", default="artifacts/agent_modelica_electrical_mutant_taskset_v0/mutants")
    parser.add_argument("--taskset-out", default="artifacts/agent_modelica_electrical_mutant_taskset_v0/taskset.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_electrical_mutant_taskset_v0/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    benchmark = _load_json(args.benchmark)
    all_tasks = benchmark.get("tasks") if isinstance(benchmark.get("tasks"), list) else []
    whitelist = [str(x) for x in (benchmark.get("component_whitelist") or []) if str(x).strip()]
    scales = [str(x).strip().lower() for x in str(args.scales).split(",") if str(x).strip()]
    requested_failure_types = [str(x).strip().lower() for x in str(args.failure_types).split(",") if str(x).strip()]
    if not requested_failure_types:
        requested_failure_types = [str(x).strip().lower() for x in str(args.failure_cycle).split(",") if str(x).strip()]
    if not requested_failure_types:
        requested_failure_types = list(DEFAULT_FAILURE_CYCLE)

    selected = _task_selection(all_tasks=all_tasks, scales=scales, max_tasks=max(0, int(args.max_tasks)))
    records: list[dict] = []
    taskset_tasks: list[dict] = []
    counts_by_failure: dict[str, int] = {}
    counts_by_scale: dict[str, int] = {}
    counts_by_category: dict[str, int] = {
        str(_failure_meta(ftype).get("category") or "unknown"): 0 for ftype in requested_failure_types
    }
    unsupported_counts_by_failure: dict[str, int] = {ftype: 0 for ftype in requested_failure_types}
    filtered_counts_by_failure: dict[str, int] = {ftype: 0 for ftype in requested_failure_types}
    reasons: list[str] = []

    for idx, task in enumerate(selected):
        task_id = str(task.get("task_id") or "")
        scale = str(task.get("scale") or "")
        ir = task.get("ir") if isinstance(task.get("ir"), dict) else {}
        ok, errors = validate_ir(ir, allowed_component_types=whitelist)
        if not ok:
            records.append(
                {
                    "task_id": task_id,
                    "scale": scale,
                    "status": "FAIL",
                    "reason": "invalid_ir",
                    "validation_errors": errors,
                }
            )
            continue
        model_text = ir_to_modelica(ir, allowed_component_types=whitelist)
        source_model_path = Path(args.source_models_dir) / f"{task_id}.mo"
        _write_text(str(source_model_path), model_text)

        if bool(args.expand_failure_types):
            failure_types_for_task = list(requested_failure_types)
        else:
            failure_types_for_task = [requested_failure_types[idx % len(requested_failure_types)]]

        for failure_type in failure_types_for_task:
            meta = _failure_meta(failure_type)
            token = _token_for(task_id=task_id, failure_type=failure_type)
            mutated_text, mutation_operator, mutated_objects = _inject_failure(
                model_text=model_text,
                ir=ir,
                failure_type=failure_type,
                token=token,
                mutation_style=str(args.mutation_style),
            )
            if mutation_operator == "none" or mutated_text == model_text:
                unsupported_counts_by_failure[failure_type] = int(unsupported_counts_by_failure.get(failure_type, 0)) + 1
                records.append(
                    {
                        "task_id": f"electrical_{task_id}_{failure_type}",
                        "origin_task_id": task_id,
                        "scale": scale,
                        "failure_type": failure_type,
                        "category": meta.get("category"),
                        "expected_stage": meta.get("expected_stage"),
                        "status": "SKIPPED",
                        "reason": "mutation_not_supported_for_failure_type",
                        "mutation_style": str(args.mutation_style),
                    }
                )
                continue
            mutated_model_path = Path(args.mutants_dir) / failure_type / f"{task_id}_{failure_type}.mo"
            _write_text(str(mutated_model_path), mutated_text)

            run_task_id = f"electrical_{task_id}_{failure_type}"
            expected_stage = str(meta.get("expected_stage") or "simulate")
            category = str(meta.get("category") or "unknown")
            mutation_operator_family = str(meta.get("mutation_operator_family") or "unknown")
            taskset_tasks.append(
                {
                    "task_id": run_task_id,
                    "scale": scale,
                    "failure_type": failure_type,
                    "category": category,
                    "expected_stage": expected_stage,
                    "source_model_path": str(source_model_path.resolve()),
                    "mutated_model_path": str(mutated_model_path.resolve()),
                    "origin_task_id": task_id,
                    "mutation_operator": mutation_operator,
                    "mutation_operator_family": mutation_operator_family,
                    "mutated_objects": mutated_objects,
                    "mutation_style": str(args.mutation_style),
                }
            )
            counts_by_failure[failure_type] = int(counts_by_failure.get(failure_type, 0)) + 1
            counts_by_scale[str(scale)] = int(counts_by_scale.get(str(scale), 0)) + 1
            counts_by_category[category] = int(counts_by_category.get(category, 0)) + 1
            records.append(
                {
                    "task_id": run_task_id,
                    "origin_task_id": task_id,
                    "scale": scale,
                    "failure_type": failure_type,
                    "category": category,
                    "expected_stage": expected_stage,
                    "status": "PASS",
                    "source_model_path": str(source_model_path.resolve()),
                    "mutated_model_path": str(mutated_model_path.resolve()),
                    "mutation_operator": mutation_operator,
                    "mutation_operator_family": mutation_operator_family,
                    "mutated_objects": mutated_objects,
                    "mutation_style": str(args.mutation_style),
                }
            )

    missing_failure_types = [ftype for ftype in requested_failure_types if int(counts_by_failure.get(ftype, 0)) <= 0]
    for ftype in missing_failure_types:
        reasons.append(f"requested_failure_type_missing:{ftype}")
        filtered_counts_by_failure[ftype] = max(
            int(filtered_counts_by_failure.get(ftype, 0)),
            max(0, len(selected) - int(unsupported_counts_by_failure.get(ftype, 0))),
        )

    status = "PASS" if taskset_tasks and not missing_failure_types else "FAIL"
    taskset = {
        "schema_version": "agent_modelica_taskset_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "live",
        "tasks": taskset_tasks,
        "sources": {"benchmark": args.benchmark},
        "selection": {
            "requested_failure_types": requested_failure_types,
            "expand_failure_types": bool(args.expand_failure_types),
            "scales": scales,
        },
    }
    summary = {
        "schema_version": "agent_modelica_electrical_mutant_taskset_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": len(taskset_tasks),
        "requested_failure_types": requested_failure_types,
        "counts_by_failure_type": counts_by_failure,
        "counts_by_category": counts_by_category,
        "counts_by_scale": counts_by_scale,
        "unsupported_counts_by_failure_type": unsupported_counts_by_failure,
        "filtered_counts_by_failure_type": filtered_counts_by_failure,
        "reasons": reasons,
        "records": records,
        "taskset_out": args.taskset_out,
        "source_models_dir": args.source_models_dir,
        "mutants_dir": args.mutants_dir,
    }
    _write_json(args.taskset_out, taskset)
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "total_tasks": len(taskset_tasks)}))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
