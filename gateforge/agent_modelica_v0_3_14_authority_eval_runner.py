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
from .agent_modelica_v0_3_13_runtime_live_evidence import classify_progressive_solve


SCHEMA_VERSION = "agent_modelica_v0_3_14_authority_eval_runner"
REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKER_IMAGE = os.environ.get("GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal")


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


def _select_tasks(tasks: list[dict], *, task_limit: int | None = None) -> list[dict]:
    selected = list(tasks)
    if task_limit is not None and int(task_limit) >= 0:
        selected = selected[: int(task_limit)]
    return selected


def _runtime_protocol(
    *,
    evaluation_label: str,
    planner_backend: str | None,
    experience_replay: str,
    planner_experience_injection: str,
    experience_source: str,
    planner_experience_max_tokens: int,
) -> dict:
    return {
        "protocol_version": "v0.3.14_authority_eval",
        "evaluation_label": str(evaluation_label or "").strip(),
        "profile_id": "repair-executor",
        "max_rounds": 6,
        "timeout_sec": 600,
        "simulate_stop_time": 10.0,
        "simulate_intervals": 500,
        "planner_backend": _norm(planner_backend),
        "experience_replay": str(experience_replay or "off"),
        "planner_experience_injection": str(planner_experience_injection or "off"),
        "experience_source": str(experience_source or ""),
        "planner_experience_max_tokens": int(planner_experience_max_tokens or 0),
        "enabled_policy_flags": {
            "source_restore_allowed": True,
            "deterministic_rules_enabled": True,
            "replay_enabled": str(experience_replay or "off") == "on",
            "planner_injection_enabled": str(planner_experience_injection or "off") == "on",
            "behavioral_contract_required": False,
            "allow_baseline_single_sweep": True,
            "allow_new_multistep_policy": True,
            "allow_branch_switch_replan_policy": True,
            "allow_same_branch_continuity_policy": False,
        },
    }


def run_one(
    task: dict,
    *,
    out_dir: Path,
    planner_backend: str | None,
    evaluation_label: str,
    experience_source: str,
    experience_replay: str,
    planner_experience_injection: str,
    planner_experience_max_tokens: int,
    timeout_sec: int = 600,
) -> dict:
    task_id = _norm(task.get("task_id"))
    protocol = _runtime_protocol(
        evaluation_label=evaluation_label,
        planner_backend=planner_backend,
        experience_replay=experience_replay,
        planner_experience_injection=planner_experience_injection,
        experience_source=experience_source,
        planner_experience_max_tokens=planner_experience_max_tokens,
    )
    with tempfile.TemporaryDirectory(prefix="gf_v0314_eval_") as td:
        tmp = Path(td)
        source_mo = tmp / "source_model.mo"
        mutated_mo = tmp / "mutated_model.mo"
        source_mo.write_text(_norm(task.get("source_model_text")), encoding="utf-8")
        mutated_mo.write_text(_norm(task.get("mutated_model_text")), encoding="utf-8")
        result_file = out_dir / f"{task_id}_result.json"
        runtime_context = AgentModelicaRuntimeContext.create(
            task_id=task_id,
            run_id=f"{task_id}_{evaluation_label}",
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
            protocol_version="v0.3.14_authority_eval",
            enabled_policy_flags=protocol["enabled_policy_flags"],
        )
        runtime_context.baseline_measurement_protocol = protocol
        runtime_context.write_json(out_dir / f"{task_id}_runtime_context.json")
        cmd = runtime_context.executor_command()
        cmd += [
            "--experience-replay",
            str(experience_replay or "off"),
            "--planner-experience-injection",
            str(planner_experience_injection or "off"),
            "--planner-experience-max-tokens",
            str(int(planner_experience_max_tokens or 0)),
        ]
        if str(experience_source or "").strip():
            cmd += ["--experience-source", str(experience_source)]
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
                "runtime_protocol": protocol,
            }
        elapsed = round(time.time() - started, 4)
        detail = _load_json(result_file)
        if detail:
            progressive = classify_progressive_solve(detail)
            success = bool(detail.get("success")) or _norm(detail.get("executor_status")).upper() == "PASS"
            experience_summary = detail.get("experience_replay") if isinstance(detail.get("experience_replay"), dict) else {}
            planner_summary = detail.get("planner_experience_injection") if isinstance(detail.get("planner_experience_injection"), dict) else {}
            replay_hit = bool(experience_summary.get("used")) or bool(planner_summary.get("used"))
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
                "experience_replay": experience_summary,
                "planner_experience_injection": planner_summary,
                "replay_hit": replay_hit,
                "v0_3_13_source_task_id": task.get("v0_3_13_source_task_id"),
                "v0_3_13_candidate_pair": task.get("v0_3_13_candidate_pair"),
                "v0_3_13_source_id": task.get("v0_3_13_source_id"),
                "v0_3_13_initialization_target_lhs": task.get("v0_3_13_initialization_target_lhs"),
                **progressive,
                "runtime_protocol": protocol,
            }
        return {
            "task_id": task_id,
            "verdict": "UNKNOWN",
            "elapsed_sec": elapsed,
            "rc": proc.returncode,
            "stdout_snippet": (proc.stdout or "")[:300],
            "stderr_snippet": (proc.stderr or "")[:300],
            "result_json_path": str(result_file.resolve()),
            "runtime_protocol": protocol,
        }


def _build_run_summary(*, rows: list[dict], planner_backend: str | None, taskset_path: str, evaluation_label: str, experience_source: str, experience_replay: str, planner_experience_injection: str) -> dict:
    total = len(rows)
    passed_rows = [row for row in rows if row.get("verdict") == "PASS"]
    progressive_rows = [row for row in passed_rows if bool(row.get("progressive_solve"))]
    non_progress_rows = [row for row in rows if row.get("verdict") != "PASS" or not bool(row.get("progressive_solve"))]
    replay_hit_count = sum(1 for row in rows if bool(row.get("replay_hit")))
    experience_replay_hit_count = sum(1 for row in rows if bool((row.get("experience_replay") or {}).get("used")))
    planner_hint_hit_count = sum(1 for row in rows if bool((row.get("planner_experience_injection") or {}).get("used")))
    rounds_on_pass = [int(row.get("rounds_used") or 0) for row in passed_rows if int(row.get("rounds_used") or 0) > 0]
    resolution_counts: dict[str, int] = {}
    for row in passed_rows:
        key = _norm(row.get("resolution_path")) or "unknown"
        resolution_counts[key] = resolution_counts.get(key, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "evaluation_label": str(evaluation_label or "").strip(),
        "taskset_path": str(Path(taskset_path).resolve()) if Path(taskset_path).exists() else str(taskset_path),
        "planner_backend": _norm(planner_backend),
        "experience_source": str(experience_source or ""),
        "experience_replay": str(experience_replay or "off"),
        "planner_experience_injection": str(planner_experience_injection or "off"),
        "total": total,
        "passed": len(passed_rows),
        "pass_rate_pct": round(100.0 * len(passed_rows) / total, 1) if total else 0.0,
        "progressive_solve_count": len(progressive_rows),
        "progressive_solve_rate_pct": round(100.0 * len(progressive_rows) / total, 1) if total else 0.0,
        "avg_rounds_on_pass": round(sum(rounds_on_pass) / float(len(rounds_on_pass)), 2) if rounds_on_pass else 0.0,
        "dead_end_or_non_progress_count": len(non_progress_rows),
        "dead_end_or_non_progress_rate_pct": round(100.0 * len(non_progress_rows) / total, 1) if total else 0.0,
        "replay_hit_count": replay_hit_count,
        "replay_hit_rate_pct": round(100.0 * replay_hit_count / total, 1) if total else 0.0,
        "experience_replay_hit_count": experience_replay_hit_count,
        "planner_hint_hit_count": planner_hint_hit_count,
        "resolution_path_counts": resolution_counts,
        "runtime_protocol": _runtime_protocol(
            evaluation_label=evaluation_label,
            planner_backend=planner_backend,
            experience_replay=experience_replay,
            planner_experience_injection=planner_experience_injection,
            experience_source=experience_source,
            planner_experience_max_tokens=400,
        ),
        "results": rows,
    }


def render_markdown(payload: dict) -> str:
    return "\n".join(
        [
            "# v0.3.14 Authority Eval Runner",
            "",
            f"- evaluation_label: `{payload.get('evaluation_label')}`",
            f"- status: `{payload.get('status')}`",
            f"- total: `{payload.get('total')}`",
            f"- passed: `{payload.get('passed')}`",
            f"- progressive_solve_rate_pct: `{payload.get('progressive_solve_rate_pct')}`",
            f"- replay_hit_rate_pct: `{payload.get('replay_hit_rate_pct')}`",
            "",
        ]
    )


def run_authority_eval(
    *,
    taskset_path: str,
    results_out_dir: str,
    out_dir: str,
    evaluation_label: str,
    experience_source: str = "",
    experience_replay: str = "off",
    planner_experience_injection: str = "off",
    planner_experience_max_tokens: int = 400,
    timeout_sec: int = 600,
    task_limit: int | None = None,
) -> dict:
    _load_dotenv()
    planner_backend = _planner_backend()
    if not planner_backend:
        raise RuntimeError("missing_planner_backend_or_model_env")
    taskset = _load_json(taskset_path)
    tasks = _select_tasks(_task_rows(taskset), task_limit=task_limit)
    if not tasks:
        raise RuntimeError("no_tasks_selected_for_v0_3_14_authority_eval")
    results_dir = Path(results_out_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        run_one(
            task,
            out_dir=results_dir,
            planner_backend=planner_backend,
            evaluation_label=evaluation_label,
            experience_source=experience_source,
            experience_replay=experience_replay,
            planner_experience_injection=planner_experience_injection,
            planner_experience_max_tokens=planner_experience_max_tokens,
            timeout_sec=timeout_sec,
        )
        for task in tasks
    ]
    summary = _build_run_summary(
        rows=rows,
        planner_backend=planner_backend,
        taskset_path=taskset_path,
        evaluation_label=evaluation_label,
        experience_source=experience_source,
        experience_replay=experience_replay,
        planner_experience_injection=planner_experience_injection,
    )
    out_root = Path(out_dir)
    _write_json(results_dir / "run_summary.json", summary)
    _write_json(out_root / "summary.json", summary)
    _write_text(out_root / "summary.md", render_markdown(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a v0.3.14 authority eval slice.")
    parser.add_argument("--taskset", required=True)
    parser.add_argument("--results-out-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--evaluation-label", required=True)
    parser.add_argument("--experience-source", default="")
    parser.add_argument("--experience-replay", choices=["on", "off"], default="off")
    parser.add_argument("--planner-experience-injection", choices=["on", "off"], default="off")
    parser.add_argument("--planner-experience-max-tokens", type=int, default=400)
    parser.add_argument("--timeout-sec", type=int, default=600)
    parser.add_argument("--task-limit", type=int, default=None)
    args = parser.parse_args()
    payload = run_authority_eval(
        taskset_path=str(args.taskset),
        results_out_dir=str(args.results_out_dir),
        out_dir=str(args.out_dir),
        evaluation_label=str(args.evaluation_label),
        experience_source=str(args.experience_source),
        experience_replay=str(args.experience_replay),
        planner_experience_injection=str(args.planner_experience_injection),
        planner_experience_max_tokens=int(args.planner_experience_max_tokens or 0),
        timeout_sec=int(args.timeout_sec),
        task_limit=args.task_limit,
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "passed": payload.get("passed"),
                "replay_hit_rate_pct": payload.get("replay_hit_rate_pct"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
