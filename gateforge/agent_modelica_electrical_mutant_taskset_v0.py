from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_modeling_ir_v0 import ir_to_modelica, validate_ir


DEFAULT_FAILURE_CYCLE = ("model_check_error", "simulate_error", "semantic_regression")
EXPECTED_STAGE_BY_FAILURE = {
    "model_check_error": "check",
    "simulate_error": "simulate",
    "semantic_regression": "simulate",
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


def _inject_failure(model_text: str, failure_type: str, token: str) -> str:
    ftype = str(failure_type or "").strip().lower()
    if ftype == "model_check_error":
        return _inject_model_check_error(model_text, token)
    if ftype == "simulate_error":
        return _inject_simulate_error(model_text, token)
    if ftype == "semantic_regression":
        return _inject_semantic_regression(model_text, token)
    return model_text


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
    failure_cycle = [str(x).strip().lower() for x in str(args.failure_cycle).split(",") if str(x).strip()]
    if not failure_cycle:
        failure_cycle = list(DEFAULT_FAILURE_CYCLE)

    selected = _task_selection(all_tasks=all_tasks, scales=scales, max_tasks=max(0, int(args.max_tasks)))
    records: list[dict] = []
    taskset_tasks: list[dict] = []
    counts_by_failure: dict[str, int] = {}
    counts_by_scale: dict[str, int] = {}

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

        failure_type = failure_cycle[idx % len(failure_cycle)]
        token = _token_for(task_id=task_id, failure_type=failure_type)
        mutated_text = _inject_failure(model_text=model_text, failure_type=failure_type, token=token)
        mutated_model_path = Path(args.mutants_dir) / failure_type / f"{task_id}_{failure_type}.mo"
        _write_text(str(mutated_model_path), mutated_text)

        run_task_id = f"electrical_{task_id}_{failure_type}"
        expected_stage = EXPECTED_STAGE_BY_FAILURE.get(failure_type, "simulate")
        taskset_tasks.append(
            {
                "task_id": run_task_id,
                "scale": scale,
                "failure_type": failure_type,
                "expected_stage": expected_stage,
                "source_model_path": str(source_model_path.resolve()),
                "mutated_model_path": str(mutated_model_path.resolve()),
                "origin_task_id": task_id,
            }
        )
        counts_by_failure[failure_type] = int(counts_by_failure.get(failure_type, 0)) + 1
        counts_by_scale[str(scale)] = int(counts_by_scale.get(str(scale), 0)) + 1
        records.append(
            {
                "task_id": run_task_id,
                "origin_task_id": task_id,
                "scale": scale,
                "failure_type": failure_type,
                "expected_stage": expected_stage,
                "status": "PASS",
                "source_model_path": str(source_model_path.resolve()),
                "mutated_model_path": str(mutated_model_path.resolve()),
            }
        )

    status = "PASS" if taskset_tasks else "FAIL"
    taskset = {
        "schema_version": "agent_modelica_taskset_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "live",
        "tasks": taskset_tasks,
        "sources": {"benchmark": args.benchmark},
    }
    summary = {
        "schema_version": "agent_modelica_electrical_mutant_taskset_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": len(taskset_tasks),
        "counts_by_failure_type": counts_by_failure,
        "counts_by_scale": counts_by_scale,
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
