from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_16_preservation_probe_taskset"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_expansion_taskset_current" / "taskset.json"
DEFAULT_RUNTIME_LIVE_SUMMARY = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_live_evidence_current" / "summary.json"
DEFAULT_INITIALIZATION_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_initialization_admitted_taskset_current" / "taskset.json"
DEFAULT_INITIALIZATION_LIVE_SUMMARY = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_initialization_live_evidence_current" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_preservation_probe_taskset_current"


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


def _task_map(taskset_payload: dict) -> dict[str, dict]:
    rows = taskset_payload.get("tasks")
    return {
        _norm(row.get("task_id")): row
        for row in (rows or [])
        if isinstance(row, dict) and _norm(row.get("task_id"))
    }


def _historical_success_rows(live_summary: dict) -> list[dict]:
    rows = live_summary.get("results")
    return [
        row for row in (rows or [])
        if isinstance(row, dict) and _norm(row.get("verdict")) == "PASS"
    ]


def _first_attempt_cluster(result_json_path: str) -> tuple[str, str]:
    detail = _load_json(result_json_path)
    attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
    first_attempt = next((row for row in attempts if isinstance(row, dict)), {})
    diagnostic = first_attempt.get("diagnostic_ir") if isinstance(first_attempt.get("diagnostic_ir"), dict) else {}
    stage_subtype = _norm(diagnostic.get("dominant_stage_subtype"))
    error_subtype = _norm(diagnostic.get("error_subtype"))
    observed_failure_type = _norm(first_attempt.get("observed_failure_type"))
    reason = _norm(first_attempt.get("reason"))
    if stage_subtype and error_subtype and error_subtype not in {"none", "unknown"}:
        return stage_subtype, f"{stage_subtype}|{error_subtype}"
    if stage_subtype and observed_failure_type and observed_failure_type not in {"none", "unknown"}:
        return stage_subtype, f"{stage_subtype}|{observed_failure_type}"
    if stage_subtype:
        return stage_subtype, stage_subtype
    return "", observed_failure_type or reason


def build_preservation_probe_taskset(
    *,
    runtime_taskset_path: str = str(DEFAULT_RUNTIME_TASKSET),
    runtime_live_summary_path: str = str(DEFAULT_RUNTIME_LIVE_SUMMARY),
    initialization_taskset_path: str = str(DEFAULT_INITIALIZATION_TASKSET),
    initialization_live_summary_path: str = str(DEFAULT_INITIALIZATION_LIVE_SUMMARY),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    runtime_task_map = _task_map(_load_json(runtime_taskset_path))
    initialization_task_map = _task_map(_load_json(initialization_taskset_path))
    tasks = []
    for lane_name, task_map, live_summary in [
        ("runtime_preservation_control_lane", runtime_task_map, _load_json(runtime_live_summary_path)),
        ("initialization_preservation_control_lane", initialization_task_map, _load_json(initialization_live_summary_path)),
    ]:
        for result_row in _historical_success_rows(live_summary):
            task = task_map.get(_norm(result_row.get("task_id")))
            if not isinstance(task, dict):
                continue
            stage_subtype, cluster = _first_attempt_cluster(_norm(result_row.get("result_json_path")))
            enriched = dict(task)
            enriched["v0_3_16_probe_lane_name"] = lane_name
            enriched["v0_3_16_expected_stage_subtype"] = stage_subtype
            enriched["v0_3_16_expected_residual_signal_cluster"] = cluster
            enriched["v0_3_16_historical_result_json_path"] = _norm(result_row.get("result_json_path"))
            tasks.append(enriched)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if tasks else "EMPTY",
        "task_count": len(tasks),
        "task_ids": [row["task_id"] for row in tasks],
        "tasks": tasks,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "taskset.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.16 Preservation Probe Taskset",
                "",
                f"- status: `{payload.get('status')}`",
                f"- task_count: `{payload.get('task_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.16 preservation probe control taskset.")
    parser.add_argument("--runtime-taskset", default=str(DEFAULT_RUNTIME_TASKSET))
    parser.add_argument("--runtime-live-summary", default=str(DEFAULT_RUNTIME_LIVE_SUMMARY))
    parser.add_argument("--initialization-taskset", default=str(DEFAULT_INITIALIZATION_TASKSET))
    parser.add_argument("--initialization-live-summary", default=str(DEFAULT_INITIALIZATION_LIVE_SUMMARY))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_preservation_probe_taskset(
        runtime_taskset_path=str(args.runtime_taskset),
        runtime_live_summary_path=str(args.runtime_live_summary),
        initialization_taskset_path=str(args.initialization_taskset),
        initialization_live_summary_path=str(args.initialization_live_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
