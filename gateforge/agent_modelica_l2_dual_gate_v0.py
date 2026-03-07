from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_modeling_ir_v0 import compare_ir_roundtrip, ir_to_modelica, modelica_to_ir, validate_ir

DEFAULT_DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"


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
        "# Agent Modelica L2 Dual Gate v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- roundtrip_pass_rate_pct: `{payload.get('roundtrip_pass_rate_pct')}`",
        f"- compile_pass_rate_pct: `{payload.get('compile_pass_rate_pct')}`",
        f"- infra_failure_count: `{payload.get('infra_failure_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((float(part) / float(total)) * 100.0, 2)


def _safe_scale_set(raw: str) -> set[str]:
    return {str(x).strip().lower() for x in str(raw or "").split(",") if str(x).strip()}


def _pick_tasks(tasks: list[dict], scales: set[str], max_tasks: int) -> list[dict]:
    rows = []
    for row in tasks:
        if not isinstance(row, dict):
            continue
        scale = str(row.get("scale") or "").lower()
        if scales and scale not in scales:
            continue
        task_id = str(row.get("task_id") or "")
        ir = row.get("ir") if isinstance(row.get("ir"), dict) else {}
        if not task_id or not ir:
            continue
        rows.append(row)
    rows = sorted(rows, key=lambda x: (str(x.get("scale") or ""), str(x.get("task_id") or "")))
    if max_tasks > 0:
        return rows[:max_tasks]
    return rows


def _run_local_omc(script_text: str, cwd: Path, timeout_sec: int) -> tuple[int | None, str]:
    script = cwd / "run.mos"
    script.write_text(script_text, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["omc", "run.mos"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_sec)),
            check=False,
        )
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return int(proc.returncode), output
    except subprocess.TimeoutExpired:
        return None, "TimeoutExpired"
    except Exception as exc:
        return None, f"{type(exc).__name__}:{exc}"


def _run_docker_omc(script_text: str, cwd: Path, timeout_sec: int, docker_image: str, cache_dir: Path) -> tuple[int | None, str]:
    script = cwd / "run.mos"
    script.write_text(script_text, encoding="utf-8")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{str(cwd)}:/workspace",
        "-v",
        f"{str(cache_dir)}:/root/.openmodelica/libraries",
        "-w",
        "/workspace",
        docker_image,
        "omc",
        "run.mos",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_sec)),
            check=False,
        )
        output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return int(proc.returncode), output
    except subprocess.TimeoutExpired:
        return None, "TimeoutExpired"
    except Exception as exc:
        return None, f"{type(exc).__name__}:{exc}"


def _check_model_ok(output: str, model_name: str) -> bool:
    text = str(output or "").lower()
    return f"check of {str(model_name).lower()} completed successfully" in text


def _classify_infra_failure(output: str) -> str:
    text = str(output or "").lower()
    if "timeoutexpired" in text or "timed out" in text:
        return "timeout"
    if "permission denied while trying to connect to the docker api" in text:
        return "docker_permission_denied"
    if "includes invalid characters for a local volume name" in text:
        return "docker_volume_mount_invalid"
    if "failed to load package modelica" in text:
        return "msl_load_failed"
    if "no such file or directory" in text:
        return "path_not_found"
    if text.startswith("filenotfounderror:"):
        return "path_not_found"
    return ""


def _model_name_from_ir(ir: dict) -> str:
    return str(ir.get("model_name") or "")


def _timeout_for_scale(
    scale: str,
    *,
    timeout_sec: int,
    timeout_small_sec: int,
    timeout_medium_sec: int,
    timeout_large_sec: int,
) -> int:
    if int(timeout_sec) > 0:
        return max(1, int(timeout_sec))
    scale_name = str(scale or "").strip().lower()
    if scale_name == "large":
        return max(1, int(timeout_large_sec))
    if scale_name == "medium":
        return max(1, int(timeout_medium_sec))
    return max(1, int(timeout_small_sec))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run L2 dual gate: IR roundtrip + OMC checkModel compile gate")
    parser.add_argument("--benchmark", default="benchmarks/agent_modelica_electrical_tasks_v0.json")
    parser.add_argument("--scales", default="small,medium")
    parser.add_argument("--max-tasks", type=int, default=0)
    parser.add_argument("--backend", choices=["openmodelica_docker", "omc"], default="openmodelica_docker")
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    parser.add_argument("--timeout-sec", type=int, default=0)
    parser.add_argument("--timeout-small-sec", type=int, default=180)
    parser.add_argument("--timeout-medium-sec", type=int, default=240)
    parser.add_argument("--timeout-large-sec", type=int, default=420)
    parser.add_argument("--cache-dir", default="artifacts/agent_modelica_l2_dual_gate_v0/.omlibrary_cache")
    parser.add_argument("--modelica-dir", default="artifacts/agent_modelica_l2_dual_gate_v0/modelica")
    parser.add_argument("--records-out", default="artifacts/agent_modelica_l2_dual_gate_v0/records.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_l2_dual_gate_v0/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    benchmark = _load_json(args.benchmark)
    whitelist = [str(x) for x in (benchmark.get("component_whitelist") or []) if str(x).strip()]
    tasks = benchmark.get("tasks") if isinstance(benchmark.get("tasks"), list) else []
    selected = _pick_tasks(tasks, _safe_scale_set(args.scales), int(args.max_tasks))
    if not selected:
        print(json.dumps({"status": "FAIL", "reason": "taskset_empty"}))
        raise SystemExit(1)

    modelica_dir = Path(args.modelica_dir)
    if not modelica_dir.is_absolute():
        modelica_dir = (Path.cwd() / modelica_dir).resolve()
    modelica_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.cache_dir)
    if not cache_dir.is_absolute():
        cache_dir = (Path.cwd() / cache_dir).resolve()

    records: list[dict] = []
    roundtrip_pass = 0
    compile_pass = 0
    infra_failure_count = 0
    infra_failure_by_reason: dict[str, int] = {}

    for task in selected:
        task_id = str(task.get("task_id") or "")
        scale = str(task.get("scale") or "unknown")
        ir = task.get("ir") if isinstance(task.get("ir"), dict) else {}
        valid, errors = validate_ir(ir, allowed_component_types=whitelist)
        row = {
            "task_id": task_id,
            "scale": scale,
            "valid_ir": bool(valid),
            "validation_errors": [str(x) for x in errors],
            "roundtrip_match": False,
            "compile_gate_pass": False,
            "compile_error_excerpt": "",
            "infra_failure_reason": "",
            "modelica_path": "",
        }
        if valid:
            modelica_text = ir_to_modelica(ir, allowed_component_types=whitelist)
            modelica_path = modelica_dir / f"{task_id}.mo"
            modelica_path.write_text(modelica_text, encoding="utf-8")
            row["modelica_path"] = str(modelica_path)
            parsed = modelica_to_ir(modelica_text)
            cmp = compare_ir_roundtrip(ir, parsed, ignore_source_meta=True)
            row["roundtrip_match"] = bool(cmp.get("match"))
            if row["roundtrip_match"]:
                roundtrip_pass += 1

            script = (
                "installPackage(Modelica);\n"
                "loadModel(Modelica);\n"
                f'loadFile("{modelica_path.name}");\n'
                f"checkModel({_model_name_from_ir(ir)});\n"
                "getErrorString();\n"
            )
            timeout_for_task = _timeout_for_scale(
                scale,
                timeout_sec=int(args.timeout_sec),
                timeout_small_sec=int(args.timeout_small_sec),
                timeout_medium_sec=int(args.timeout_medium_sec),
                timeout_large_sec=int(args.timeout_large_sec),
            )
            if args.backend == "omc":
                _rc, output = _run_local_omc(script, cwd=modelica_dir, timeout_sec=timeout_for_task)
            else:
                _rc, output = _run_docker_omc(
                    script,
                    cwd=modelica_dir,
                    timeout_sec=timeout_for_task,
                    docker_image=str(args.docker_image),
                    cache_dir=cache_dir,
                )
            row["compile_gate_pass"] = _check_model_ok(output, _model_name_from_ir(ir))
            if row["compile_gate_pass"]:
                compile_pass += 1
            else:
                row["compile_error_excerpt"] = str(output or "")[:1200]
                infra = _classify_infra_failure(output)
                if infra:
                    row["infra_failure_reason"] = infra
                    infra_failure_count += 1
                    infra_failure_by_reason[infra] = int(infra_failure_by_reason.get(infra, 0)) + 1

        records.append(row)

    total = len(records)
    roundtrip_rate = _ratio(roundtrip_pass, total)
    compile_rate = _ratio(compile_pass, total)
    status = "PASS" if roundtrip_rate == 100.0 and compile_rate == 100.0 and infra_failure_count == 0 else "FAIL"
    summary = {
        "schema_version": "agent_modelica_l2_dual_gate_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "benchmark_path": args.benchmark,
        "scales": sorted(list(_safe_scale_set(args.scales))),
        "backend": args.backend,
        "docker_image": args.docker_image if args.backend == "openmodelica_docker" else "",
        "timeout_profile_sec": {
            "small": int(args.timeout_small_sec),
            "medium": int(args.timeout_medium_sec),
            "large": int(args.timeout_large_sec),
            "override": int(args.timeout_sec),
        },
        "total_tasks": total,
        "roundtrip_pass_count": roundtrip_pass,
        "roundtrip_pass_rate_pct": roundtrip_rate,
        "compile_pass_count": compile_pass,
        "compile_pass_rate_pct": compile_rate,
        "infra_failure_count": infra_failure_count,
        "infra_failure_by_reason": {k: infra_failure_by_reason[k] for k in sorted(infra_failure_by_reason.keys())},
        "records_out": args.records_out,
    }
    _write_json(args.records_out, {"records": records})
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": status,
                "total_tasks": total,
                "roundtrip_pass_rate_pct": roundtrip_rate,
                "compile_pass_rate_pct": compile_rate,
                "infra_failure_count": infra_failure_count,
            }
        )
    )
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
