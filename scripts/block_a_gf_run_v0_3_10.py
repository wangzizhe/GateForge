#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_runtime_context_v1 import AgentModelicaRuntimeContext  # noqa: E402
from gateforge.agent_modelica_same_branch_continuity_family_spec_v0_3_10 import (  # noqa: E402
    BASELINE_LEVER_NAME,
    BASELINE_PROTOCOL_VERSION,
    BASELINE_REFERENCE_VERSION,
)
from gateforge.agent_modelica_same_branch_continuity_taskset_v0_3_10 import (  # noqa: E402
    build_same_branch_continuity_taskset,
)


DEFAULT_TASKSET_DIR = REPO_ROOT / "artifacts" / "agent_modelica_same_branch_continuity_taskset_v0_3_10"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_block_a_gf_results_v0_3_10"
DOCKER_IMAGE = os.environ.get("GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal")


def _load_dotenv() -> None:
    for env_path in [pathlib.Path.cwd() / ".env", REPO_ROOT / ".env"]:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
            break


def _planner_backend() -> str | None:
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def _load_taskset(taskset_path: pathlib.Path) -> list[dict]:
    if not taskset_path.exists():
        build_same_branch_continuity_taskset(out_dir=str(DEFAULT_TASKSET_DIR))
    payload = json.loads(taskset_path.read_text(encoding="utf-8"))
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _load_result(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _baseline_protocol(planner_backend: str | None) -> dict:
    return {
        "protocol_version": BASELINE_PROTOCOL_VERSION,
        "baseline_lever_name": BASELINE_LEVER_NAME,
        "baseline_reference_version": BASELINE_REFERENCE_VERSION,
        "profile_id": "repair-executor",
        "max_rounds": 6,
        "timeout_sec": 600,
        "simulate_stop_time": 10.0,
        "simulate_intervals": 500,
        "planner_backend": str(planner_backend or ""),
        "enabled_policy_flags": {
            "source_restore_allowed": True,
            "deterministic_rules_enabled": True,
            "replay_enabled": True,
            "planner_injection_enabled": True,
            "behavioral_contract_required": False,
            "allow_baseline_single_sweep": True,
            "allow_new_multistep_policy": False,
            "allow_branch_switch_replan_policy": False,
            "allow_same_branch_continuity_policy": False,
        },
    }


def run_one(task: dict, out_dir: pathlib.Path) -> dict:
    task_id = str(task.get("task_id") or "")
    with tempfile.TemporaryDirectory(prefix="gf_v0310_run_") as td:
        tmp = pathlib.Path(td)
        source_mo = tmp / "source_model.mo"
        mutated_mo = tmp / "mutated_model.mo"
        source_mo.write_text(str(task.get("source_model_text") or ""), encoding="utf-8")
        mutated_mo.write_text(str(task.get("mutated_model_text") or ""), encoding="utf-8")
        result_file = out_dir / f"{task_id}_result.json"
        runtime_context = AgentModelicaRuntimeContext.create(
            task_id=task_id,
            run_id=f"{task_id}_v0310_same_branch_continuity_baseline",
            arm_kind="gateforge",
            profile_id="repair-executor",
            artifact_root=out_dir,
            source_model_path=source_mo,
            mutated_model_path=mutated_mo,
            result_path=result_file,
            declared_failure_type=str(task.get("declared_failure_type") or "simulate_error"),
            expected_stage=str(task.get("expected_stage") or "simulate"),
            max_rounds=6,
            simulate_stop_time=10.0,
            simulate_intervals=500,
            timeout_sec=600,
            planner_backend=_planner_backend(),
            omc_backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            protocol_version=BASELINE_PROTOCOL_VERSION,
            enabled_policy_flags={
                "allow_baseline_single_sweep": True,
                "allow_new_multistep_policy": False,
                "allow_branch_switch_replan_policy": False,
                "allow_same_branch_continuity_policy": False,
            },
        )
        runtime_context.baseline_measurement_protocol = _baseline_protocol(runtime_context.planner_backend)
        runtime_context.write_json(out_dir / f"{task_id}_runtime_context.json")
        cmd = runtime_context.executor_command()
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(REPO_ROOT),
                env={**os.environ, "PATH": "/usr/local/bin:" + os.environ.get("PATH", "")},
            )
        except subprocess.TimeoutExpired:
            return {
                "task_id": task_id,
                "verdict": "TIMEOUT",
                "elapsed_sec": time.time() - t0,
                "result_json_path": str(result_file.resolve()),
                "baseline_measurement_protocol": runtime_context.baseline_measurement_protocol,
                "selected_branch": task.get("selected_branch"),
                "current_branch": task.get("current_branch"),
                "same_branch_continuity_design": task.get("same_branch_continuity_design"),
            }

        elapsed = time.time() - t0
        result_json = _load_result(result_file)
        if result_json:
            success = bool(result_json.get("success")) or result_json.get("executor_status") == "PASS"
            return {
                "task_id": task_id,
                "verdict": "PASS" if success else "FAIL",
                "executor_status": result_json.get("executor_status"),
                "planner_invoked": result_json.get("planner_invoked"),
                "rounds_used": result_json.get("rounds_used"),
                "resolution_path": result_json.get("resolution_path"),
                "llm_request_count": int(result_json.get("llm_request_count") or result_json.get("llm_request_count_delta") or 0),
                "check_model_pass": result_json.get("check_model_pass"),
                "simulate_pass": result_json.get("simulate_pass"),
                "error_message": result_json.get("error_message"),
                "elapsed_sec": elapsed,
                "result_json_path": str(result_file.resolve()),
                "selected_branch": task.get("selected_branch"),
                "current_branch": task.get("current_branch"),
                "same_branch_continuity_design": task.get("same_branch_continuity_design"),
                "baseline_measurement_protocol": runtime_context.baseline_measurement_protocol,
            }

        return {
            "task_id": task_id,
            "verdict": "UNKNOWN",
            "elapsed_sec": elapsed,
            "rc": proc.returncode,
            "stdout_snippet": (proc.stdout or "")[:200],
            "stderr_snippet": (proc.stderr or "")[:200],
            "result_json_path": str(result_file.resolve()),
            "selected_branch": task.get("selected_branch"),
            "current_branch": task.get("current_branch"),
            "same_branch_continuity_design": task.get("same_branch_continuity_design"),
            "baseline_measurement_protocol": runtime_context.baseline_measurement_protocol,
        }


def main() -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Run the v0.3.10 Block A baseline authority setup.")
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_DIR / "taskset.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_RESULTS_DIR))
    args = parser.parse_args()

    backend = _planner_backend()
    if not backend:
        print("ERROR: Set GEMINI_API_KEY/GOOGLE_API_KEY or OPENAI_API_KEY before running.")
        return 1

    taskset_path = pathlib.Path(args.taskset)
    tasks = _load_taskset(taskset_path)
    if not tasks:
        print("ERROR: No tasks available for v0.3.10 Block A run.")
        return 1

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [run_one(task, out_dir) for task in tasks]
    total = len(rows)
    passed = sum(1 for row in rows if row.get("verdict") == "PASS")
    planner_invoked_count = sum(1 for row in rows if row.get("planner_invoked") is True)
    deterministic_only_count = sum(1 for row in rows if str(row.get("resolution_path") or "") == "deterministic_rule_only")
    summary = {
        "total": total,
        "passed": passed,
        "planner_invoked_count": planner_invoked_count,
        "planner_invoked_pct": round(100.0 * planner_invoked_count / total, 1) if total else 0.0,
        "deterministic_only_count": deterministic_only_count,
        "deterministic_only_pct": round(100.0 * deterministic_only_count / total, 1) if total else 0.0,
        "baseline_measurement_protocol": rows[0].get("baseline_measurement_protocol") if rows else _baseline_protocol(backend),
        "results": rows,
    }
    summary_path = out_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary saved to: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
