#!/usr/bin/env python3
"""
Block A GateForge runner for v0.3.6 post-restore harder-lane candidates.

This is the fixed baseline authority run for the v0.3.6 harder-lane gate:
  - uses the v0.3.5 single-sweep lever as baseline
  - disables any new multistep policy
  - writes baseline measurement protocol into the run summary

Usage:
  source .env
  python3 scripts/block_a_gf_run_v0_3_6.py
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import argparse

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_post_restore_taskset_v0_3_6 import (
    build_post_restore_taskset,
)
from gateforge.agent_modelica_runtime_context_v1 import AgentModelicaRuntimeContext

DEFAULT_TASKSET_DIR = REPO_ROOT / "artifacts" / "agent_modelica_post_restore_taskset_v0_3_6"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_block_a_gf_results_v0_3_6"
DOCKER_IMAGE = os.environ.get(
    "GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal"
)


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
        build_post_restore_taskset(out_dir=str(DEFAULT_TASKSET_DIR))
    payload = json.loads(taskset_path.read_text(encoding="utf-8"))
    rows = payload.get("tasks")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _load_result(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_one(task: dict, out_dir: pathlib.Path) -> dict:
    task_id = str(task.get("task_id") or "")
    print(f"\n{'=' * 60}")
    print(f"[{task_id}]")
    with tempfile.TemporaryDirectory(prefix="gf_v036_run_") as td:
        tmp = pathlib.Path(td)
        source_mo = tmp / "source_model.mo"
        mutated_mo = tmp / "mutated_model.mo"
        source_mo.write_text(str(task.get("source_model_text") or ""), encoding="utf-8")
        mutated_mo.write_text(str(task.get("mutated_model_text") or ""), encoding="utf-8")
        result_file = out_dir / f"{task_id}_result.json"
        runtime_context = AgentModelicaRuntimeContext.create(
            task_id=task_id,
            run_id=f"{task_id}_v036_baseline_authority",
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
            enabled_policy_flags={
                "allow_baseline_single_sweep": True,
                "allow_new_multistep_policy": False,
            },
        )
        runtime_context.write_json(out_dir / f"{task_id}_runtime_context.json")
        cmd = runtime_context.executor_command()
        print(f"  planner-backend: {runtime_context.planner_backend}")
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
            elapsed = time.time() - t0
            print(f"  TIMEOUT after {elapsed:.0f}s")
            return {"task_id": task_id, "verdict": "TIMEOUT", "elapsed_sec": elapsed}

        elapsed = time.time() - t0
        result_json = _load_result(result_file)
        if result_json:
            planner_invoked = result_json.get("planner_invoked")
            rounds_used = result_json.get("rounds_used")
            resolution_path = result_json.get("resolution_path")
            success = bool(result_json.get("success")) or result_json.get("executor_status") == "PASS"
            row = {
                "task_id": task_id,
                "verdict": "PASS" if success else "FAIL",
                "planner_invoked": planner_invoked,
                "rounds_used": rounds_used,
                "resolution_path": resolution_path,
                "llm_request_count": int(
                    result_json.get("llm_request_count")
                    or result_json.get("llm_request_count_delta")
                    or 0
                ),
                "elapsed_sec": elapsed,
                "baseline_measurement_protocol": runtime_context.baseline_measurement_protocol,
            }
            print(
                f"  elapsed={elapsed:.1f}s rc={proc.returncode} planner={planner_invoked} "
                f"rounds={rounds_used} resolution={resolution_path} success={success}"
            )
            return row

        print(f"  rc={proc.returncode} no structured result file")
        return {
            "task_id": task_id,
            "verdict": "UNKNOWN",
            "elapsed_sec": elapsed,
            "rc": proc.returncode,
            "stdout_snippet": (proc.stdout or "")[:200],
            "stderr_snippet": (proc.stderr or "")[:200],
            "baseline_measurement_protocol": runtime_context.baseline_measurement_protocol,
        }


def main() -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Run the v0.3.6 Block A baseline authority setup.")
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
        print("ERROR: No tasks available for v0.3.6 Block A run.")
        return 1

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Running GateForge on {len(tasks)} v0.3.6 candidates")
    print(f"  planner backend: {backend}")
    print(f"  results dir: {out_dir}")
    print(f"  taskset: {taskset_path}")

    rows = [run_one(task, out_dir) for task in tasks]
    total = len(rows)
    passed = sum(1 for row in rows if row.get("verdict") == "PASS")
    planner_invoked_count = sum(1 for row in rows if row.get("planner_invoked") is True)
    deterministic_only_count = sum(
        1 for row in rows if str(row.get("resolution_path") or "") == "deterministic_rule_only"
    )
    summary = {
        "total": total,
        "passed": passed,
        "planner_invoked_count": planner_invoked_count,
        "planner_invoked_pct": round(100.0 * planner_invoked_count / total, 1) if total else 0.0,
        "deterministic_only_count": deterministic_only_count,
        "deterministic_only_pct": round(100.0 * deterministic_only_count / total, 1) if total else 0.0,
        "baseline_measurement_protocol": rows[0].get("baseline_measurement_protocol") if rows else {},
        "results": rows,
    }
    summary_path = out_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary saved to: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
