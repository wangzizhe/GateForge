from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_runtime_context_v1 import AgentModelicaRuntimeContext
from .agent_modelica_v0_3_12_block_b_decision import build_v0_3_12_block_b_decision
from .agent_modelica_v0_3_12_candidate_refresh import refresh_v0_3_12_candidates
from .agent_modelica_v0_3_12_one_shot_classifier import build_v0_3_12_one_shot_classifier
from .agent_modelica_v0_3_12_one_shot_family_spec import build_lane_summary_from_taskset
from .agent_modelica_v0_3_12_one_shot_taskset import (
    BASELINE_LEVER_NAME,
    BASELINE_PROTOCOL_VERSION,
    BASELINE_REFERENCE_VERSION,
    build_v0_3_12_one_shot_taskset,
)


SCHEMA_VERSION = "agent_modelica_v0_3_12_block_b_runner"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKSET_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_12_one_shot_taskset_current"
DEFAULT_FAMILY_SPEC_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_12_one_shot_family_spec_current"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_block_b_gf_results_v0_3_12_current"
DEFAULT_REFRESH_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_12_candidate_refresh_current"
DEFAULT_CLASSIFIER_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_12_one_shot_classifier_current"
DEFAULT_DECISION_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_12_block_b_decision_current"
DEFAULT_RUNNER_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_12_block_b_runner_current"
DOCKER_IMAGE = os.environ.get("GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_dotenv() -> None:
    for env_path in [Path.cwd() / ".env", REPO_ROOT / ".env"]:
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
    explicit = str(
        os.environ.get("LLM_PROVIDER")
        or os.environ.get("GATEFORGE_LIVE_PLANNER_BACKEND")
        or ""
    ).strip().lower()
    if explicit in {"gemini", "openai", "rule"}:
        return explicit
    model = (
        str(os.environ.get("LLM_MODEL") or "").strip()
        or str(os.environ.get("OPENAI_MODEL") or "").strip()
        or str(os.environ.get("GATEFORGE_GEMINI_MODEL") or "").strip()
        or str(os.environ.get("GEMINI_MODEL") or "").strip()
    )
    lower = model.lower()
    if lower.startswith("gpt"):
        return "openai"
    if "gemini" in lower:
        return "gemini"
    return None


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def select_tasks(tasks: list[dict], *, task_ids: list[str] | None = None, task_limit: int | None = None) -> list[dict]:
    wanted = {str(item).strip() for item in (task_ids or []) if str(item).strip()}
    selected = [task for task in tasks if not wanted or str(task.get("task_id") or "") in wanted]
    if task_limit is not None and task_limit >= 0:
        selected = selected[:task_limit]
    return selected


def run_one(task: dict, *, out_dir: Path, planner_backend: str | None, timeout_sec: int = 600) -> dict:
    task_id = str(task.get("task_id") or "")
    with tempfile.TemporaryDirectory(prefix="gf_v0312_run_") as td:
        tmp = Path(td)
        source_mo = tmp / "source_model.mo"
        mutated_mo = tmp / "mutated_model.mo"
        source_mo.write_text(str(task.get("source_model_text") or ""), encoding="utf-8")
        mutated_mo.write_text(str(task.get("mutated_model_text") or ""), encoding="utf-8")
        result_file = out_dir / f"{task_id}_result.json"
        runtime_context = AgentModelicaRuntimeContext.create(
            task_id=task_id,
            run_id=f"{task_id}_v0312_one_shot_baseline",
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
            timeout_sec=timeout_sec,
            planner_backend=str(planner_backend or ""),
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
        runtime_context.baseline_measurement_protocol = _baseline_protocol(planner_backend)
        runtime_context.write_json(out_dir / f"{task_id}_runtime_context.json")
        cmd = runtime_context.executor_command()
        started = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(REPO_ROOT),
                env={**os.environ, "PATH": "/usr/local/bin:" + os.environ.get("PATH", "")},
            )
        except subprocess.TimeoutExpired:
            return {
                "task_id": task_id,
                "verdict": "TIMEOUT",
                "elapsed_sec": round(time.time() - started, 4),
                "result_json_path": str(result_file.resolve()),
                "selected_branch": task.get("selected_branch"),
                "current_branch": task.get("current_branch"),
                "preferred_branch": task.get("preferred_branch"),
                "baseline_measurement_protocol": runtime_context.baseline_measurement_protocol,
            }

        elapsed = round(time.time() - started, 4)
        result_json = _load_json(result_file)
        if result_json:
            success = bool(result_json.get("success")) or str(result_json.get("executor_status") or "").upper() == "PASS"
            return {
                "task_id": task_id,
                "verdict": "PASS" if success else "FAIL",
                "executor_status": result_json.get("executor_status"),
                "planner_invoked": result_json.get("planner_invoked"),
                "planner_used": result_json.get("planner_used"),
                "planner_decisive": result_json.get("planner_decisive"),
                "rounds_used": result_json.get("rounds_used"),
                "resolution_path": result_json.get("resolution_path"),
                "llm_request_count": int(result_json.get("llm_request_count") or result_json.get("llm_request_count_delta") or 0),
                "check_model_pass": result_json.get("check_model_pass"),
                "simulate_pass": result_json.get("simulate_pass"),
                "physics_contract_pass": result_json.get("physics_contract_pass"),
                "error_message": result_json.get("error_message"),
                "elapsed_sec": elapsed,
                "result_json_path": str(result_file.resolve()),
                "selected_branch": task.get("selected_branch"),
                "current_branch": task.get("current_branch"),
                "preferred_branch": task.get("preferred_branch"),
                "candidate_branches": task.get("candidate_branches"),
                "candidate_next_branches": task.get("candidate_next_branches"),
                "v0_3_12_one_shot_design": task.get("v0_3_12_one_shot_design"),
                "baseline_measurement_protocol": runtime_context.baseline_measurement_protocol,
            }

        return {
            "task_id": task_id,
            "verdict": "UNKNOWN",
            "elapsed_sec": elapsed,
            "rc": proc.returncode,
            "stdout_snippet": (proc.stdout or "")[:300],
            "stderr_snippet": (proc.stderr or "")[:300],
            "result_json_path": str(result_file.resolve()),
            "selected_branch": task.get("selected_branch"),
            "current_branch": task.get("current_branch"),
            "preferred_branch": task.get("preferred_branch"),
            "candidate_branches": task.get("candidate_branches"),
            "candidate_next_branches": task.get("candidate_next_branches"),
            "v0_3_12_one_shot_design": task.get("v0_3_12_one_shot_design"),
            "baseline_measurement_protocol": runtime_context.baseline_measurement_protocol,
        }


def _build_run_summary(*, rows: list[dict], planner_backend: str | None) -> dict:
    total = len(rows)
    passed = sum(1 for row in rows if row.get("verdict") == "PASS")
    planner_invoked_count = sum(1 for row in rows if row.get("planner_invoked") is True)
    deterministic_only_count = sum(1 for row in rows if str(row.get("resolution_path") or "") == "deterministic_rule_only")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "total": total,
        "passed": passed,
        "planner_invoked_count": planner_invoked_count,
        "planner_invoked_pct": round(100.0 * planner_invoked_count / total, 1) if total else 0.0,
        "deterministic_only_count": deterministic_only_count,
        "deterministic_only_pct": round(100.0 * deterministic_only_count / total, 1) if total else 0.0,
        "baseline_measurement_protocol": _baseline_protocol(planner_backend),
        "results": rows,
    }


def run_v0_3_12_block_b(
    *,
    taskset_out_dir: str = str(DEFAULT_TASKSET_DIR),
    family_spec_out_dir: str = str(DEFAULT_FAMILY_SPEC_DIR),
    results_out_dir: str = str(DEFAULT_RESULTS_DIR),
    refresh_out_dir: str = str(DEFAULT_REFRESH_DIR),
    classifier_out_dir: str = str(DEFAULT_CLASSIFIER_DIR),
    decision_out_dir: str = str(DEFAULT_DECISION_DIR),
    runner_out_dir: str = str(DEFAULT_RUNNER_DIR),
    task_ids: list[str] | None = None,
    task_limit: int | None = None,
    timeout_sec: int = 600,
) -> dict:
    _load_dotenv()
    planner_backend = _planner_backend()
    if not planner_backend:
        raise RuntimeError("missing_planner_backend_or_model_env")

    taskset = build_v0_3_12_one_shot_taskset(out_dir=taskset_out_dir)
    family_spec = build_lane_summary_from_taskset(
        candidate_taskset_path=str(Path(taskset_out_dir) / "taskset.json"),
        out_dir=family_spec_out_dir,
    )
    if str(family_spec.get("lane_status") or "") != "CANDIDATE_READY":
        raise RuntimeError(
            f"candidate_lane_not_ready:{family_spec.get('lane_status')}:{family_spec.get('admitted_count')}"
        )

    tasks = select_tasks(_task_rows(taskset), task_ids=task_ids, task_limit=task_limit)
    if not tasks:
        raise RuntimeError("no_tasks_selected_for_v0_3_12_block_b")

    results_dir = Path(results_out_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    rows = [run_one(task, out_dir=results_dir, planner_backend=planner_backend, timeout_sec=timeout_sec) for task in tasks]
    run_summary = _build_run_summary(rows=rows, planner_backend=planner_backend)
    run_summary_path = results_dir / "run_summary.json"
    _write_json(run_summary_path, run_summary)

    refreshed = refresh_v0_3_12_candidates(
        candidate_taskset_path=str(Path(taskset_out_dir) / "taskset.json"),
        results_path=str(run_summary_path),
        out_dir=refresh_out_dir,
    )
    classifier = build_v0_3_12_one_shot_classifier(
        refreshed_summary_path=str(Path(refresh_out_dir) / "summary.json"),
        out_dir=classifier_out_dir,
    )
    decision = build_v0_3_12_block_b_decision(
        lane_summary_path=str(Path(family_spec_out_dir) / "summary.json"),
        classifier_summary_path=str(Path(classifier_out_dir) / "summary.json"),
        out_dir=decision_out_dir,
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "planner_backend": planner_backend,
        "task_count": len(tasks),
        "task_ids": [str(task.get("task_id") or "") for task in tasks],
        "paths": {
            "taskset_summary_path": str((Path(taskset_out_dir) / "taskset.json").resolve()),
            "family_spec_summary_path": str((Path(family_spec_out_dir) / "summary.json").resolve()),
            "run_summary_path": str(run_summary_path.resolve()),
            "refresh_summary_path": str((Path(refresh_out_dir) / "summary.json").resolve()),
            "classifier_summary_path": str((Path(classifier_out_dir) / "summary.json").resolve()),
            "decision_summary_path": str((Path(decision_out_dir) / "summary.json").resolve()),
        },
        "lane_status": family_spec.get("lane_status"),
        "admitted_count": family_spec.get("admitted_count"),
        "successful_labeled_count": (classifier.get("metrics") or {}).get("successful_labeled_count"),
        "unknown_success_pct": (classifier.get("metrics") or {}).get("unknown_success_pct"),
        "true_continuity_pct": (classifier.get("metrics") or {}).get("true_continuity_pct"),
        "decision": decision.get("decision"),
    }
    runner_root = Path(runner_out_dir)
    _write_json(runner_root / "summary.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.12 Block B one-shot baseline authority pipeline.")
    parser.add_argument("--taskset-out-dir", default=str(DEFAULT_TASKSET_DIR))
    parser.add_argument("--family-spec-out-dir", default=str(DEFAULT_FAMILY_SPEC_DIR))
    parser.add_argument("--results-out-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--refresh-out-dir", default=str(DEFAULT_REFRESH_DIR))
    parser.add_argument("--classifier-out-dir", default=str(DEFAULT_CLASSIFIER_DIR))
    parser.add_argument("--decision-out-dir", default=str(DEFAULT_DECISION_DIR))
    parser.add_argument("--runner-out-dir", default=str(DEFAULT_RUNNER_DIR))
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--task-limit", type=int, default=None)
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    try:
        payload = run_v0_3_12_block_b(
            taskset_out_dir=str(args.taskset_out_dir),
            family_spec_out_dir=str(args.family_spec_out_dir),
            results_out_dir=str(args.results_out_dir),
            refresh_out_dir=str(args.refresh_out_dir),
            classifier_out_dir=str(args.classifier_out_dir),
            decision_out_dir=str(args.decision_out_dir),
            runner_out_dir=str(args.runner_out_dir),
            task_ids=list(args.task_id or []),
            task_limit=args.task_limit,
            timeout_sec=int(args.timeout_sec),
        )
    except RuntimeError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}))
        return 1
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "task_count": payload.get("task_count"),
                "decision": payload.get("decision"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
