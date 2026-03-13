from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_action_applier_v0 import apply_repair_actions_to_modelica_v0
from .agent_modelica_diagnostic_ir_v0 import build_diagnostic_ir_v0
from .agent_modelica_l4_orchestrator_v0 import build_provenance_repair_candidates_v0
from .agent_modelica_live_executor_gemini_v1 import (
    DEFAULT_DOCKER_IMAGE,
    _find_primary_model_name,
    _read_text,
    _run_omc_script_docker,
    _run_omc_script_local,
)
from .agent_modelica_run_contract_v1 import _task_diagnostic_context_hints


SCHEMA_VERSION = "agent_modelica_connector_fast_check_v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_md(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent Modelica Connector Fast Check v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- pass_count: `{payload.get('pass_count')}`",
        f"- diagnosis_pass_count: `{payload.get('diagnosis_pass_count')}`",
        f"- action_apply_pass_count: `{payload.get('action_apply_pass_count')}`",
        f"- repair_check_pass_count: `{payload.get('repair_check_pass_count')}`",
        f"- stage_match_rate_pct: `{payload.get('stage_match_rate_pct')}`",
        f"- reasons: `{payload.get('reasons')}`",
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _blocked_reason(output: str) -> str:
    lower = str(output or "").lower()
    if "permission denied while trying to connect to the docker api" in lower:
        return "docker_unavailable"
    if "failed to load package modelica" in lower:
        return "modelica_package_unavailable"
    if "class modelica." in lower and "not found in scope" in lower:
        return "modelica_package_unavailable"
    return ""


def _check_ok_from_output(output: str) -> bool:
    lower = str(output or "").lower()
    return "check of" in lower and "completed successfully" in lower


def _check_model_text_once(*, model_text: str, backend: str, docker_image: str, timeout_sec: int, task: dict) -> dict:
    model_name = _find_primary_model_name(model_text)
    if not model_name:
        diagnostic = build_diagnostic_ir_v0(
            output="Model name not found",
            check_model_pass=False,
            simulate_pass=True,
            expected_stage=str(task.get("expected_stage") or "check"),
            declared_failure_type=str(task.get("failure_type") or ""),
            declared_context_hints=_task_diagnostic_context_hints(task),
        )
        return {
            "check_model_pass": False,
            "rc": None,
            "output": "Model name not found",
            "diagnostic_ir": diagnostic,
        }

    with tempfile.TemporaryDirectory() as d:
        workspace = Path(d)
        local_model = workspace / "candidate.mo"
        local_model.write_text(model_text, encoding="utf-8")
        script = (
            "installPackage(Modelica);\n"
            "getErrorString();\n"
            "loadModel(Modelica);\n"
            "getErrorString();\n"
            f'loadFile("{local_model.name}");\n'
            "getErrorString();\n"
            f"checkModel({model_name});\n"
            "getErrorString();\n"
        )
        if backend == "omc":
            rc, output = _run_omc_script_local(script, timeout_sec=timeout_sec, cwd=str(workspace))
        else:
            rc, output = _run_omc_script_docker(script, timeout_sec=timeout_sec, cwd=str(workspace), image=docker_image)
    check_ok = _check_ok_from_output(output)
    diagnostic = build_diagnostic_ir_v0(
        output=output,
        check_model_pass=bool(check_ok),
        simulate_pass=True,
        expected_stage=str(task.get("expected_stage") or "check"),
        declared_failure_type=str(task.get("failure_type") or ""),
        declared_context_hints=_task_diagnostic_context_hints(task),
    )
    return {
        "check_model_pass": bool(check_ok),
        "rc": rc,
        "output": output,
        "diagnostic_ir": diagnostic,
    }


def _check_model_once(*, model_path: str, backend: str, docker_image: str, timeout_sec: int, task: dict) -> dict:
    return _check_model_text_once(
        model_text=_read_text(Path(model_path)),
        backend=backend,
        docker_image=docker_image,
        timeout_sec=timeout_sec,
        task=task,
    )


def build_connector_fast_check_v1(
    *,
    taskset_payload: dict,
    backend: str = "openmodelica_docker",
    docker_image: str = DEFAULT_DOCKER_IMAGE,
    timeout_sec: int = 30,
    runner=None,
) -> dict:
    tasks = taskset_payload.get("tasks") if isinstance(taskset_payload.get("tasks"), list) else []
    tasks = [
        row
        for row in tasks
        if isinstance(row, dict) and str(row.get("failure_type") or "").strip().lower() == "connector_mismatch"
    ]
    check_runner = runner or (
        lambda task, model_text=None: _check_model_text_once(
            model_text=model_text if model_text is not None else _read_text(Path(str(task.get("mutated_model_path") or ""))),
            backend=backend,
            docker_image=docker_image,
            timeout_sec=timeout_sec,
            task=task,
        )
    )

    results: list[dict] = []
    pass_count = 0
    diagnosis_pass_count = 0
    action_apply_pass_count = 0
    repair_check_pass_count = 0
    blocked_count = 0
    stage_match_count = 0
    reasons: list[str] = []

    for task in tasks:
        task_id = str(task.get("task_id") or "")
        expected_stage = str(task.get("expected_stage") or "check").strip().lower() or "check"
        model_text = _read_text(Path(str(task.get("mutated_model_path") or "")))
        initial = check_runner(task, model_text)
        diagnostic = initial.get("diagnostic_ir") if isinstance(initial.get("diagnostic_ir"), dict) else {}
        error_type = str(diagnostic.get("error_type") or "none")
        error_subtype = str(diagnostic.get("error_subtype") or "none")
        stage = str(diagnostic.get("stage") or "none")
        observed_phase = str(diagnostic.get("observed_phase") or "none")
        stage_match = stage == expected_stage
        if stage_match:
            stage_match_count += 1
        blocked_reason = _blocked_reason(str(initial.get("output") or ""))
        diagnosis_pass = (
            not bool(initial.get("check_model_pass"))
            and error_type == "model_check_error"
            and error_subtype == "connector_mismatch"
            and stage_match
        )
        if diagnosis_pass:
            diagnosis_pass_count += 1
        provenance_candidates = build_provenance_repair_candidates_v0(
            task=task,
            diagnostic_payload=diagnostic,
            ir_payload=None,
        )
        selected = [
            row for row in provenance_candidates
            if isinstance(row, dict)
            and isinstance(row.get("action"), dict)
            and str((row.get("action") or {}).get("op") or "").strip().lower() == "rewrite_connection_endpoint"
        ]
        action_payload = [selected[0]["action"]] if selected else []
        apply_summary = apply_repair_actions_to_modelica_v0(
            modelica_text=model_text,
            actions_payload=action_payload,
            max_actions_per_round=1,
        ) if action_payload else {"status": "FAIL", "apply_error_code": "no_connector_rewrite_action"}
        apply_pass = str(apply_summary.get("status") or "") == "PASS"
        if apply_pass:
            action_apply_pass_count += 1
        patched_check = {}
        patched_pass = False
        if apply_pass:
            patched_text = str(apply_summary.get("updated_modelica_text") or "")
            patched_check = check_runner(task, patched_text)
            patched_pass = bool(patched_check.get("check_model_pass"))
            if patched_pass:
                repair_check_pass_count += 1
        if blocked_reason:
            blocked_count += 1
            reasons.append(f"blocked:{blocked_reason}:{task_id}")
        elif diagnosis_pass and apply_pass and patched_pass:
            pass_count += 1
        else:
            reasons.append(f"task_failed_fast_check:{task_id}")
        results.append(
            {
                "task_id": task_id,
                "expected_stage": expected_stage,
                "mutated_model_path": str(task.get("mutated_model_path") or ""),
                "initial_check_model_pass": bool(initial.get("check_model_pass")),
                "initial_error_type": error_type,
                "initial_error_subtype": error_subtype,
                "initial_stage": stage,
                "initial_observed_phase": observed_phase,
                "stage_match": stage_match,
                "blocked_reason": blocked_reason,
                "planned_action_op": str(action_payload[0].get("op") or "") if action_payload else "",
                "planned_action_target": action_payload[0].get("target") if action_payload else {},
                "apply_status": str(apply_summary.get("status") or ""),
                "apply_error_code": str(apply_summary.get("apply_error_code") or ""),
                "patched_check_model_pass": patched_pass,
                "patched_error_type": str(((patched_check.get("diagnostic_ir") or {}).get("error_type") or "")) if isinstance(patched_check, dict) else "",
                "patched_error_subtype": str(((patched_check.get("diagnostic_ir") or {}).get("error_subtype") or "")) if isinstance(patched_check, dict) else "",
                "rc": initial.get("rc"),
            }
        )

    total_tasks = len(tasks)
    status = "PASS" if total_tasks > 0 and pass_count == total_tasks else "FAIL"
    if total_tasks <= 0:
        status = "FAIL"
        reasons.append("no_connector_tasks")
    elif blocked_count > 0:
        status = "BLOCKED"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "status": status,
        "backend": backend,
        "docker_image": docker_image if backend == "openmodelica_docker" else "",
        "timeout_sec": int(timeout_sec),
        "total_tasks": total_tasks,
        "pass_count": pass_count,
        "diagnosis_pass_count": diagnosis_pass_count,
        "action_apply_pass_count": action_apply_pass_count,
        "repair_check_pass_count": repair_check_pass_count,
        "blocked_count": blocked_count,
        "stage_match_rate_pct": round((stage_match_count / total_tasks) * 100.0, 2) if total_tasks else 0.0,
        "task_results": results,
        "reasons": sorted(set(reasons)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run check-only fast check for connector mismatch realism tasks")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--backend", choices=["omc", "openmodelica_docker"], default="openmodelica_docker")
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE)
    parser.add_argument("--timeout-sec", type=int, default=30)
    parser.add_argument("--out", default="artifacts/agent_modelica_connector_fast_check_v1/summary.json")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    summary = build_connector_fast_check_v1(
        taskset_payload=_load_json(args.taskset),
        backend=str(args.backend),
        docker_image=str(args.docker_image),
        timeout_sec=int(args.timeout_sec),
    )
    _write_json(args.out, summary)
    _write_md(args.report_out or str(Path(args.out).with_suffix(".md")), summary)
    print(json.dumps(summary))
    if str(summary.get("status") or "") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
