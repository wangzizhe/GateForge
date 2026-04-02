from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_runtime_context_v1 import AgentModelicaRuntimeContext


SCHEMA_VERSION = "agent_modelica_v0_3_13_runtime_live_evidence"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKSET_PATH = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_expansion_taskset_current" / "taskset.json"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_live_results_current"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_live_evidence_current"
DOCKER_IMAGE = os.environ.get("GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal")
PROTOCOL_VERSION = "v0.3.13_runtime_multiround_expansion"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_dotenv() -> None:
    for env_path in [Path.cwd() / ".env", REPO_ROOT / ".env"]:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            text = str(line or "").strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, _, value = text.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


def _planner_backend() -> str | None:
    explicit = _norm(
        os.environ.get("LLM_PROVIDER")
        or os.environ.get("GATEFORGE_LIVE_PLANNER_BACKEND")
    ).lower()
    if explicit in {"gemini", "openai", "rule"}:
        return explicit
    model = (
        _norm(os.environ.get("LLM_MODEL"))
        or _norm(os.environ.get("OPENAI_MODEL"))
        or _norm(os.environ.get("GATEFORGE_GEMINI_MODEL"))
        or _norm(os.environ.get("GEMINI_MODEL"))
    ).lower()
    if model.startswith("gpt"):
        return "openai"
    if "gemini" in model:
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


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def select_tasks(tasks: list[dict], *, task_ids: list[str] | None = None, task_limit: int | None = None) -> list[dict]:
    wanted = {str(item).strip() for item in (task_ids or []) if str(item).strip()}
    selected = [task for task in tasks if not wanted or _norm(task.get("task_id")) in wanted]
    if task_limit is not None and task_limit >= 0:
        selected = selected[:task_limit]
    return selected


def _runtime_protocol(planner_backend: str | None) -> dict:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "profile_id": "repair-executor",
        "max_rounds": 6,
        "timeout_sec": 600,
        "simulate_stop_time": 10.0,
        "simulate_intervals": 500,
        "planner_backend": _norm(planner_backend),
        "enabled_policy_flags": {
            "source_restore_allowed": True,
            "deterministic_rules_enabled": True,
            "replay_enabled": True,
            "planner_injection_enabled": True,
            "behavioral_contract_required": False,
            "allow_baseline_single_sweep": True,
            "allow_new_multistep_policy": True,
            "allow_branch_switch_replan_policy": True,
            "allow_same_branch_continuity_policy": False,
        },
    }


def _attempt_rows(detail: dict) -> list[dict]:
    rows = detail.get("attempts")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _bool_seq(rows: list[dict], key: str) -> list[bool]:
    out: list[bool] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, bool):
            out.append(value)
    return out


def _has_false_then_true(values: list[bool]) -> bool:
    seen_false = False
    for value in values:
        if value is False:
            seen_false = True
        elif value is True and seen_false:
            return True
    return False


def classify_progressive_solve(detail: dict) -> dict:
    attempts = _attempt_rows(detail)
    executor_status = _norm(detail.get("executor_status")).upper()
    resolution_path = _norm(detail.get("resolution_path"))
    rounds_used = int(detail.get("rounds_used") or len(attempts) or 0)
    runtime_hygiene = detail.get("executor_runtime_hygiene") if isinstance(detail.get("executor_runtime_hygiene"), dict) else {}
    planner_event_count = int(runtime_hygiene.get("planner_event_count") or 0)
    check_progress = _has_false_then_true(_bool_seq(attempts, "check_model_pass"))
    simulate_progress = _has_false_then_true(_bool_seq(attempts, "simulate_pass"))
    signals = []
    if rounds_used >= 2:
        signals.append("multi_round_execution")
    if planner_event_count > 0:
        signals.append("planner_event_observed")
    if check_progress:
        signals.append("check_model_recovery")
    if simulate_progress:
        signals.append("simulate_recovery")
    progressive = (
        executor_status == "PASS"
        and resolution_path != "deterministic_rule_only"
        and rounds_used >= 2
        and bool(signals)
    )
    return {
        "progressive_solve": progressive,
        "progress_signal_labels": signals,
        "planner_event_count": planner_event_count,
        "rounds_used": rounds_used,
        "check_model_recovery": check_progress,
        "simulate_recovery": simulate_progress,
    }


def run_one(task: dict, *, out_dir: Path, planner_backend: str | None, timeout_sec: int = 600) -> dict:
    task_id = _norm(task.get("task_id"))
    with tempfile.TemporaryDirectory(prefix="gf_v0313_runtime_live_") as td:
        tmp = Path(td)
        source_mo = tmp / "source_model.mo"
        mutated_mo = tmp / "mutated_model.mo"
        source_mo.write_text(_norm(task.get("source_model_text")), encoding="utf-8")
        mutated_mo.write_text(_norm(task.get("mutated_model_text")), encoding="utf-8")
        result_file = out_dir / f"{task_id}_result.json"
        runtime_context = AgentModelicaRuntimeContext.create(
            task_id=task_id,
            run_id=f"{task_id}_v0313_runtime_expansion",
            arm_kind="gateforge",
            profile_id="repair-executor",
            artifact_root=out_dir,
            source_model_path=source_mo,
            mutated_model_path=mutated_mo,
            result_path=result_file,
            declared_failure_type=_norm(task.get("declared_failure_type") or "simulate_error"),
            expected_stage=_norm(task.get("expected_stage") or "simulate"),
            max_rounds=6,
            simulate_stop_time=10.0,
            simulate_intervals=500,
            timeout_sec=timeout_sec,
            planner_backend=_norm(planner_backend),
            omc_backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
            protocol_version=PROTOCOL_VERSION,
            enabled_policy_flags=_runtime_protocol(planner_backend)["enabled_policy_flags"],
        )
        runtime_context.baseline_measurement_protocol = _runtime_protocol(planner_backend)
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
                "runtime_protocol": runtime_context.baseline_measurement_protocol,
            }
        elapsed = round(time.time() - started, 4)
        detail = _load_json(result_file)
        if detail:
            progressive = classify_progressive_solve(detail)
            success = bool(detail.get("success")) or _norm(detail.get("executor_status")).upper() == "PASS"
            return {
                "task_id": task_id,
                "verdict": "PASS" if success else "FAIL",
                "executor_status": detail.get("executor_status"),
                "planner_invoked": detail.get("planner_invoked"),
                "planner_used": detail.get("planner_used"),
                "planner_decisive": detail.get("planner_decisive"),
                "rounds_used": detail.get("rounds_used"),
                "resolution_path": detail.get("resolution_path"),
                "check_model_pass": detail.get("check_model_pass"),
                "simulate_pass": detail.get("simulate_pass"),
                "physics_contract_pass": detail.get("physics_contract_pass"),
                "contract_pass": detail.get("contract_pass"),
                "elapsed_sec": elapsed,
                "result_json_path": str(result_file.resolve()),
                "executor_runtime_hygiene": detail.get("executor_runtime_hygiene"),
                "v0_3_13_source_task_id": task.get("v0_3_13_source_task_id"),
                "v0_3_13_candidate_pair": task.get("v0_3_13_candidate_pair"),
                **progressive,
                "runtime_protocol": runtime_context.baseline_measurement_protocol,
            }
        return {
            "task_id": task_id,
            "verdict": "UNKNOWN",
            "elapsed_sec": elapsed,
            "rc": proc.returncode,
            "stdout_snippet": (proc.stdout or "")[:300],
            "stderr_snippet": (proc.stderr or "")[:300],
            "result_json_path": str(result_file.resolve()),
            "runtime_protocol": runtime_context.baseline_measurement_protocol,
        }


def _build_run_summary(*, rows: list[dict], planner_backend: str | None, taskset_path: str) -> dict:
    total = len(rows)
    passed_rows = [row for row in rows if row.get("verdict") == "PASS"]
    progressive_rows = [row for row in passed_rows if bool(row.get("progressive_solve"))]
    deterministic_only_count = sum(1 for row in passed_rows if _norm(row.get("resolution_path")) == "deterministic_rule_only")
    multiround_success_count = sum(1 for row in passed_rows if int(row.get("rounds_used") or 0) >= 2)
    planner_invoked_count = sum(1 for row in rows if row.get("planner_invoked") is True)
    by_resolution_path: dict[str, int] = {}
    for row in passed_rows:
        key = _norm(row.get("resolution_path")) or "unknown"
        by_resolution_path[key] = by_resolution_path.get(key, 0) + 1
    by_source_task_id: dict[str, int] = {}
    for row in progressive_rows:
        key = _norm(row.get("v0_3_13_source_task_id")) or "unknown"
        by_source_task_id[key] = by_source_task_id.get(key, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "taskset_path": str(Path(taskset_path).resolve()) if Path(taskset_path).exists() else str(taskset_path),
        "planner_backend": _norm(planner_backend),
        "total": total,
        "passed": len(passed_rows),
        "pass_rate_pct": round(100.0 * len(passed_rows) / total, 1) if total else 0.0,
        "planner_invoked_count": planner_invoked_count,
        "planner_invoked_pct": round(100.0 * planner_invoked_count / total, 1) if total else 0.0,
        "deterministic_only_count": deterministic_only_count,
        "multiround_success_count": multiround_success_count,
        "progressive_solve_count": len(progressive_rows),
        "progressive_solve_rate_pct": round(100.0 * len(progressive_rows) / total, 1) if total else 0.0,
        "resolution_path_counts": by_resolution_path,
        "progressive_by_source_task_id": by_source_task_id,
        "runtime_protocol": _runtime_protocol(planner_backend),
        "results": rows,
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# v0.3.13 Runtime Live Evidence",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total: `{payload.get('total')}`",
        f"- passed: `{payload.get('passed')}`",
        f"- multiround_success_count: `{payload.get('multiround_success_count')}`",
        f"- progressive_solve_count: `{payload.get('progressive_solve_count')}`",
        f"- progressive_solve_rate_pct: `{payload.get('progressive_solve_rate_pct')}`",
        "",
    ]
    return "\n".join(lines)


def run_runtime_live_evidence(
    *,
    taskset_path: str = str(DEFAULT_TASKSET_PATH),
    results_out_dir: str = str(DEFAULT_RESULTS_DIR),
    out_dir: str = str(DEFAULT_OUT_DIR),
    task_ids: list[str] | None = None,
    task_limit: int | None = None,
    timeout_sec: int = 600,
) -> dict:
    _load_dotenv()
    planner_backend = _planner_backend()
    if not planner_backend:
        raise RuntimeError("missing_planner_backend_or_model_env")
    taskset = _load_json(taskset_path)
    tasks = select_tasks(_task_rows(taskset), task_ids=task_ids, task_limit=task_limit)
    if not tasks:
        raise RuntimeError("no_tasks_selected_for_v0_3_13_runtime_live_evidence")
    results_dir = Path(results_out_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    rows = [run_one(task, out_dir=results_dir, planner_backend=planner_backend, timeout_sec=timeout_sec) for task in tasks]
    summary = _build_run_summary(rows=rows, planner_backend=planner_backend, taskset_path=taskset_path)
    out_root = Path(out_dir)
    _write_json(results_dir / "run_summary.json", summary)
    _write_json(out_root / "summary.json", summary)
    _write_text(out_root / "summary.md", render_markdown(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.3.13 runtime live evidence on the admitted expansion lane.")
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_PATH))
    parser.add_argument("--results-out-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--task-limit", type=int, default=None)
    parser.add_argument("--timeout-sec", type=int, default=600)
    args = parser.parse_args()
    payload = run_runtime_live_evidence(
        taskset_path=str(args.taskset),
        results_out_dir=str(args.results_out_dir),
        out_dir=str(args.out_dir),
        task_ids=[str(x) for x in (args.task_id or []) if str(x).strip()],
        task_limit=args.task_limit,
        timeout_sec=int(args.timeout_sec),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "passed": payload.get("passed"),
                "progressive_solve_count": payload.get("progressive_solve_count"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
