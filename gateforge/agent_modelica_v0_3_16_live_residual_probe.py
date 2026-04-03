from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_runtime_context_v1 import AgentModelicaRuntimeContext


SCHEMA_VERSION = "agent_modelica_v0_3_16_live_residual_probe"
REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKER_IMAGE = os.environ.get("GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal")
DEFAULT_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_preservation_probe_taskset_current" / "taskset.json"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_live_residual_probe_results_current"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_live_residual_probe_current"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _residual_cluster(attempt: dict) -> tuple[str, str]:
    diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
    stage_subtype = _norm(diagnostic.get("dominant_stage_subtype"))
    error_subtype = _norm(diagnostic.get("error_subtype"))
    observed_failure_type = _norm(attempt.get("observed_failure_type"))
    reason = _norm(attempt.get("reason"))
    if stage_subtype and error_subtype and error_subtype not in {"none", "unknown"}:
        return stage_subtype, f"{stage_subtype}|{error_subtype}"
    if stage_subtype and observed_failure_type and observed_failure_type not in {"none", "unknown"}:
        return stage_subtype, f"{stage_subtype}|{observed_failure_type}"
    if stage_subtype:
        return stage_subtype, stage_subtype
    return "", observed_failure_type or reason


def run_probe_one(task: dict, *, results_out_dir: Path, timeout_sec: int) -> dict:
    task_id = _norm(task.get("task_id"))
    with tempfile.TemporaryDirectory(prefix="gf_v0316_probe_") as td:
        tmp = Path(td)
        source_mo = tmp / "source_model.mo"
        mutated_mo = tmp / "mutated_model.mo"
        source_mo.write_text(_norm(task.get("source_model_text")), encoding="utf-8")
        mutated_mo.write_text(_norm(task.get("mutated_model_text")), encoding="utf-8")
        result_file = results_out_dir / f"{task_id}_result.json"
        runtime_context = AgentModelicaRuntimeContext.create(
            task_id=task_id,
            run_id=f"{task_id}_v0316_probe",
            arm_kind="gateforge",
            profile_id="repair-executor",
            artifact_root=results_out_dir,
            source_model_path=source_mo,
            mutated_model_path=mutated_mo,
            result_path=result_file,
            declared_failure_type=_norm(task.get("declared_failure_type") or "simulate_error"),
            expected_stage=_norm(task.get("expected_stage") or "simulate"),
            max_rounds=2,
            simulate_stop_time=10.0,
            simulate_intervals=500,
            timeout_sec=timeout_sec,
            planner_backend="rule",
            omc_backend="openmodelica_docker",
            docker_image=DOCKER_IMAGE,
        )
        cmd = runtime_context.executor_command() + [
            "--experience-replay",
            "off",
            "--planner-experience-injection",
            "off",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=timeout_sec,
            env={**os.environ, "PATH": "/usr/local/bin:" + os.environ.get("PATH", "")},
        )
        detail = _load_json(result_file)
        attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
        first_attempt = next((row for row in attempts if isinstance(row, dict)), {})
        second_attempt = next((row for row in attempts[1:] if isinstance(row, dict)), {})
        probe_attempt = second_attempt if second_attempt else first_attempt
        stage_subtype, cluster = _residual_cluster(probe_attempt if probe_attempt else {})
        expected_stage = _norm(task.get("v0_3_16_expected_stage_subtype"))
        expected_cluster = _norm(task.get("v0_3_16_expected_residual_signal_cluster"))
        admitted = bool(stage_subtype and cluster and stage_subtype == expected_stage and cluster == expected_cluster)
        return {
            "task_id": task_id,
            "probe_lane_name": _norm(task.get("v0_3_16_probe_lane_name")),
            "historical_expected_stage_subtype": expected_stage,
            "historical_expected_residual_signal_cluster": expected_cluster,
            "probe_stage_subtype": stage_subtype,
            "probe_residual_signal_cluster": cluster,
            "probe_matches_historical": admitted,
            "executor_status": _norm(detail.get("executor_status")) if detail else "",
            "result_json_path": str(result_file.resolve()),
            "return_code": proc.returncode,
        }


def run_live_residual_probe(
    *,
    taskset_path: str = str(DEFAULT_TASKSET),
    results_out_dir: str = str(DEFAULT_RESULTS_DIR),
    out_dir: str = str(DEFAULT_OUT_DIR),
    timeout_sec: int = 120,
) -> dict:
    taskset = _load_json(taskset_path)
    tasks = _task_rows(taskset)
    results_dir = Path(results_out_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    rows = [run_probe_one(task, results_out_dir=results_dir, timeout_sec=timeout_sec) for task in tasks]
    admitted = [row for row in rows if bool(row.get("probe_matches_historical"))]
    lane_counts: dict[str, int] = {}
    mismatch_stage_counts: dict[str, int] = {}
    for row in rows:
        lane = _norm(row.get("probe_lane_name")) or "unknown"
        lane_counts[lane] = lane_counts.get(lane, 0) + int(bool(row.get("probe_matches_historical")))
        key = _norm(row.get("probe_stage_subtype")) or "unknown"
        mismatch_stage_counts[key] = mismatch_stage_counts.get(key, 0) + 1
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "probe_mode": "deterministic_cleanup_then_executor_omc_probe",
        "taskset_path": str(Path(taskset_path).resolve()) if Path(taskset_path).exists() else str(taskset_path),
        "task_count": len(rows),
        "probe_admitted_candidate_count": len(admitted),
        "probe_admitted_rate_pct": round(100.0 * len(admitted) / float(len(rows)), 1) if rows else 0.0,
        "lane_admitted_counts": lane_counts,
        "observed_probe_stage_counts": mismatch_stage_counts,
        "rows": rows,
    }
    out_root = Path(out_dir)
    admitted_taskset = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if admitted else "EMPTY",
        "task_count": len(admitted),
        "task_ids": [row["task_id"] for row in admitted],
        "tasks": [task for task in tasks if _norm(task.get("task_id")) in {row["task_id"] for row in admitted}],
    }
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "admitted_taskset.json", admitted_taskset)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.16 Live Residual Probe",
                "",
                f"- status: `{payload.get('status')}`",
                f"- probe_admitted_candidate_count: `{payload.get('probe_admitted_candidate_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.16 live residual preservation probe.")
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET))
    parser.add_argument("--results-out-dir", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout-sec", type=int, default=120)
    args = parser.parse_args()
    payload = run_live_residual_probe(
        taskset_path=str(args.taskset),
        results_out_dir=str(args.results_out_dir),
        out_dir=str(args.out_dir),
        timeout_sec=int(args.timeout_sec),
    )
    print(json.dumps({"status": payload.get("status"), "probe_admitted_candidate_count": payload.get("probe_admitted_candidate_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
