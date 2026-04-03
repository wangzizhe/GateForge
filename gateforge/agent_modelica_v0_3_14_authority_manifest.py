from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_versioned_ci_fixtures import materialize_v0314_authority_fixture


SCHEMA_VERSION = "agent_modelica_v0_3_14_authority_manifest"
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RUNTIME_WORK_ORDER = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_live_work_order_current" / "summary.json"
DEFAULT_RUNTIME_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_expansion_taskset_current" / "taskset.json"
DEFAULT_RUNTIME_LIVE_SUMMARY = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_live_evidence_current" / "summary.json"

DEFAULT_INITIALIZATION_WORK_ORDER = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_initialization_live_work_order_current" / "summary.json"
DEFAULT_INITIALIZATION_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_initialization_admitted_taskset_current" / "taskset.json"
DEFAULT_INITIALIZATION_LIVE_SUMMARY = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_initialization_live_evidence_current" / "summary.json"

DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_authority_manifest_current"

RUNTIME_TRAIN_TASK_IDS = (
    "v036_rlc_dual_collapse__pair_r_c__preview",
    "v036_heater_dual_collapse__pair_c_q__preview",
    "v036_thermal_rc_dual_collapse__pair_cth_tenv__preview",
)

RUNTIME_EVAL_TASK_IDS = (
    "v036_rlc_dual_collapse__pair_l_c__preview",
    "v036_tank_dual_collapse__pair_a_qin__preview",
    "v036_heater_dual_collapse__pair_c_tenv__preview",
    "v036_thermal_rc_dual_collapse__pair_rth_tenv__preview",
    "v036_hydraulic_ar_dual_collapse__pair_a_qin__preview",
    "v036_hydraulic_ar_dual_collapse__pair_r_qin__preview",
    "v036_mix_vtau_dual_collapse__pair_v_cin__preview",
    "v036_mix_vtau_dual_collapse__pair_tau_cin__preview",
)

INITIALIZATION_TRAIN_TASK_IDS = (
    "init_log_sqrt__lhs_x__preview",
    "init_dual_sqrt__lhs_x_fast__preview",
)

INITIALIZATION_EVAL_TASK_IDS = (
    "init_log_sqrt__lhs_y__preview",
    "init_dual_sqrt__lhs_x_slow__preview",
    "init_log_growth__lhs_y__preview",
    "init_log_growth__lhs_x__preview",
)


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
    rows = taskset_payload.get("tasks") if isinstance(taskset_payload.get("tasks"), list) else []
    return {_norm(row.get("task_id")): row for row in rows if isinstance(row, dict) and _norm(row.get("task_id"))}


def _result_map(live_summary_payload: dict) -> dict[str, dict]:
    rows = live_summary_payload.get("results") if isinstance(live_summary_payload.get("results"), list) else []
    return {_norm(row.get("task_id")): row for row in rows if isinstance(row, dict) and _norm(row.get("task_id"))}


def _select_entries(
    *,
    task_ids: tuple[str, ...],
    task_map: dict[str, dict],
    result_map: dict[str, dict],
    lane_name: str,
    role: str,
) -> tuple[list[dict], list[str]]:
    entries: list[dict] = []
    missing: list[str] = []
    for task_id in task_ids:
        task_row = task_map.get(task_id)
        result_row = result_map.get(task_id)
        if not isinstance(task_row, dict) or not isinstance(result_row, dict):
            missing.append(task_id)
            continue
        result_path = Path(_norm(result_row.get("result_json_path")))
        detail = _load_json(result_path)
        attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
        entry = {
            "task_id": task_id,
            "lane_name": lane_name,
            "role": role,
            "task_json_path": _norm(task_row.get("task_json_path")),
            "result_json_path": str(result_path.resolve()) if result_path.exists() else str(result_path),
            "rounds_used": int(result_row.get("rounds_used") or 0),
            "resolution_path": _norm(result_row.get("resolution_path")),
            "planner_event_count": int(result_row.get("planner_event_count") or ((detail.get("executor_runtime_hygiene") or {}).get("planner_event_count") or 0)),
            "attempt_count": len([row for row in attempts if isinstance(row, dict)]),
            "trace_available": bool(result_path.exists() and attempts),
            "source_task_id": _norm(result_row.get("v0_3_13_source_task_id") or result_row.get("v0_3_13_source_id")),
            "candidate_pair": list(result_row.get("v0_3_13_candidate_pair") or []),
            "initialization_target_lhs": _norm(result_row.get("v0_3_13_initialization_target_lhs")),
        }
        entries.append(entry)
    return entries, missing


def _failure_bank_entries(
    *,
    result_map: dict[str, dict],
    lane_name: str,
) -> list[dict]:
    rows = []
    for row in result_map.values():
        if _norm(row.get("verdict")) != "FAIL":
            continue
        result_path = Path(_norm(row.get("result_json_path")))
        detail = _load_json(result_path)
        attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
        rows.append(
            {
                "task_id": _norm(row.get("task_id")),
                "lane_name": lane_name,
                "role": "failure_bank",
                "result_json_path": str(result_path.resolve()) if result_path.exists() else str(result_path),
                "rounds_used": int(row.get("rounds_used") or 0),
                "resolution_path": _norm(row.get("resolution_path")),
                "planner_event_count": int(row.get("planner_event_count") or ((detail.get("executor_runtime_hygiene") or {}).get("planner_event_count") or 0)),
                "attempt_count": len([item for item in attempts if isinstance(item, dict)]),
                "trace_available": bool(result_path.exists() and attempts),
                "source_task_id": _norm(row.get("v0_3_13_source_task_id") or row.get("v0_3_13_source_id")),
            }
        )
    return rows


def _build_taskset(task_ids: tuple[str, ...], task_map: dict[str, dict]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "task_count": len(task_ids),
        "tasks": [task_map[task_id] for task_id in task_ids if task_id in task_map],
    }


def _trace_summary(entries: list[dict], failure_entries: list[dict]) -> dict:
    rows = [row for row in entries + failure_entries if isinstance(row, dict)]
    attempt_missing = sum(1 for row in rows if int(row.get("attempt_count") or 0) <= 0)
    planner_missing = sum(1 for row in rows if int(row.get("planner_event_count") or 0) < 0)
    resolution_missing = sum(1 for row in rows if not _norm(row.get("resolution_path")))
    missing_trace = sum(1 for row in rows if not bool(row.get("trace_available")))
    status = "PASS" if attempt_missing == 0 and resolution_missing == 0 and missing_trace == 0 else "FAIL"
    return {
        "status": status,
        "checked_result_count": len(rows),
        "trace_available_count": len(rows) - missing_trace,
        "missing_trace_count": missing_trace,
        "missing_attempt_count": attempt_missing,
        "missing_planner_event_count": planner_missing,
        "missing_resolution_path_count": resolution_missing,
    }


def build_authority_manifest(
    *,
    runtime_work_order_path: str = str(DEFAULT_RUNTIME_WORK_ORDER),
    runtime_taskset_path: str = str(DEFAULT_RUNTIME_TASKSET),
    runtime_live_summary_path: str = str(DEFAULT_RUNTIME_LIVE_SUMMARY),
    initialization_work_order_path: str = str(DEFAULT_INITIALIZATION_WORK_ORDER),
    initialization_taskset_path: str = str(DEFAULT_INITIALIZATION_TASKSET),
    initialization_live_summary_path: str = str(DEFAULT_INITIALIZATION_LIVE_SUMMARY),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    default_input_paths = (
        runtime_work_order_path,
        runtime_taskset_path,
        runtime_live_summary_path,
        initialization_work_order_path,
        initialization_taskset_path,
        initialization_live_summary_path,
    )
    if any(not Path(path).exists() for path in default_input_paths):
        fixture_paths = materialize_v0314_authority_fixture(out_dir)
        runtime_work_order_path = fixture_paths["runtime_work_order_path"]
        runtime_taskset_path = fixture_paths["runtime_taskset_path"]
        runtime_live_summary_path = fixture_paths["runtime_live_summary_path"]
        initialization_work_order_path = fixture_paths["initialization_work_order_path"]
        initialization_taskset_path = fixture_paths["initialization_taskset_path"]
        initialization_live_summary_path = fixture_paths["initialization_live_summary_path"]

    runtime_work_order = _load_json(runtime_work_order_path)
    initialization_work_order = _load_json(initialization_work_order_path)
    runtime_task_map = _task_map(_load_json(runtime_taskset_path))
    initialization_task_map = _task_map(_load_json(initialization_taskset_path))
    runtime_result_map = _result_map(_load_json(runtime_live_summary_path))
    initialization_result_map = _result_map(_load_json(initialization_live_summary_path))

    runtime_train, runtime_train_missing = _select_entries(
        task_ids=RUNTIME_TRAIN_TASK_IDS,
        task_map=runtime_task_map,
        result_map=runtime_result_map,
        lane_name="runtime_authority_lane",
        role="experience_source",
    )
    runtime_eval, runtime_eval_missing = _select_entries(
        task_ids=RUNTIME_EVAL_TASK_IDS,
        task_map=runtime_task_map,
        result_map=runtime_result_map,
        lane_name="runtime_authority_lane",
        role="eval",
    )
    initialization_train, initialization_train_missing = _select_entries(
        task_ids=INITIALIZATION_TRAIN_TASK_IDS,
        task_map=initialization_task_map,
        result_map=initialization_result_map,
        lane_name="initialization_selective_lane",
        role="experience_source",
    )
    initialization_eval, initialization_eval_missing = _select_entries(
        task_ids=INITIALIZATION_EVAL_TASK_IDS,
        task_map=initialization_task_map,
        result_map=initialization_result_map,
        lane_name="initialization_selective_lane",
        role="eval",
    )

    runtime_failure_bank = _failure_bank_entries(result_map=runtime_result_map, lane_name="runtime_authority_lane")
    initialization_failure_bank = _failure_bank_entries(result_map=initialization_result_map, lane_name="initialization_selective_lane")

    trace_summary = _trace_summary(
        runtime_train + runtime_eval + initialization_train + initialization_eval,
        runtime_failure_bank + initialization_failure_bank,
    )
    missing_ids = runtime_train_missing + runtime_eval_missing + initialization_train_missing + initialization_eval_missing
    status = "PASS" if not missing_ids and trace_summary.get("status") == "PASS" else "FAIL"

    out_root = Path(out_dir)
    runtime_eval_taskset_path = out_root / "runtime_eval_taskset.json"
    initialization_eval_taskset_path = out_root / "initialization_eval_taskset.json"
    _write_json(runtime_eval_taskset_path, _build_taskset(RUNTIME_EVAL_TASK_IDS, runtime_task_map))
    _write_json(initialization_eval_taskset_path, _build_taskset(INITIALIZATION_EVAL_TASK_IDS, initialization_task_map))

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "trace_availability": trace_summary,
        "runtime": {
            "authority_status": _norm(runtime_work_order.get("runtime_lane_status")),
            "experience_source_count": len(runtime_train),
            "eval_count": len(runtime_eval),
            "experience_sources": runtime_train,
            "eval_tasks": runtime_eval,
            "eval_taskset_path": str(runtime_eval_taskset_path.resolve()),
        },
        "initialization": {
            "authority_status": _norm(initialization_work_order.get("initialization_lane_status")),
            "experience_source_count": len(initialization_train),
            "eval_count": len(initialization_eval),
            "experience_sources": initialization_train,
            "eval_tasks": initialization_eval,
            "eval_taskset_path": str(initialization_eval_taskset_path.resolve()),
        },
        "failure_bank": {
            "runtime_failed_count": len(runtime_failure_bank),
            "initialization_failed_count": len(initialization_failure_bank),
            "runtime_failures": runtime_failure_bank,
            "initialization_failures": initialization_failure_bank,
        },
        "excluded_lanes": [
            "legacy_initialization_seed_lane",
            "tank_coupled_initialization_failures_from_main_eval",
        ],
        "missing_task_ids": missing_ids,
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "trace_availability_status": trace_summary.get("status"),
        "runtime_experience_source_count": len(runtime_train),
        "runtime_eval_count": len(runtime_eval),
        "initialization_experience_source_count": len(initialization_train),
        "initialization_eval_count": len(initialization_eval),
        "failure_bank_count": len(runtime_failure_bank) + len(initialization_failure_bank),
        "missing_task_id_count": len(missing_ids),
        "trace_availability": trace_summary,
    }
    _write_json(out_root / "manifest.json", manifest)
    _write_json(out_root / "summary.json", summary)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.14 Authority Manifest",
                "",
                f"- status: `{status}`",
                f"- trace_availability_status: `{trace_summary.get('status')}`",
                f"- runtime_experience_source_count: `{len(runtime_train)}`",
                f"- runtime_eval_count: `{len(runtime_eval)}`",
                f"- initialization_experience_source_count: `{len(initialization_train)}`",
                f"- initialization_eval_count: `{len(initialization_eval)}`",
                f"- failure_bank_count: `{len(runtime_failure_bank) + len(initialization_failure_bank)}`",
                "",
            ]
        ),
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the v0.3.14 authority substrate manifest.")
    parser.add_argument("--runtime-work-order", default=str(DEFAULT_RUNTIME_WORK_ORDER))
    parser.add_argument("--runtime-taskset", default=str(DEFAULT_RUNTIME_TASKSET))
    parser.add_argument("--runtime-live-summary", default=str(DEFAULT_RUNTIME_LIVE_SUMMARY))
    parser.add_argument("--initialization-work-order", default=str(DEFAULT_INITIALIZATION_WORK_ORDER))
    parser.add_argument("--initialization-taskset", default=str(DEFAULT_INITIALIZATION_TASKSET))
    parser.add_argument("--initialization-live-summary", default=str(DEFAULT_INITIALIZATION_LIVE_SUMMARY))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_authority_manifest(
        runtime_work_order_path=str(args.runtime_work_order),
        runtime_taskset_path=str(args.runtime_taskset),
        runtime_live_summary_path=str(args.runtime_live_summary),
        initialization_work_order_path=str(args.initialization_work_order),
        initialization_taskset_path=str(args.initialization_taskset),
        initialization_live_summary_path=str(args.initialization_live_summary),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "runtime_eval_count": ((payload.get("runtime") or {}).get("eval_count") or 0),
                "initialization_eval_count": ((payload.get("initialization") or {}).get("eval_count") or 0),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
