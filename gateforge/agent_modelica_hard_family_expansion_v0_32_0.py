from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_loader_v0_29_0 import load_and_validate_task
from .agent_modelica_hard_benchmark_gate_v0_29_1 import audit_hard_benchmark_task

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_family_expansion_v0_32_0"

V0320_CASE_IDS = (
    "sem_13_arrayed_connector_bus_refactor",
    "sem_14_inherited_probe_adapter_drift",
    "sem_15_commanded_load_contract_drift",
    "sem_16_arrayed_current_adapter_drift",
    "sem_17_bridge_monitor_contract_drift",
    "sem_18_transducer_role_migration",
)


def _task_path(task_root: Path, case_id: str) -> Path:
    return task_root / f"{case_id}.json"


def build_hard_family_expansion_summary(
    *,
    task_root: Path = DEFAULT_TASK_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
    case_ids: tuple[str, ...] = V0320_CASE_IDS,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    validation_errors: dict[str, list[str]] = {}
    for case_id in case_ids:
        path = _task_path(task_root, case_id)
        task, errors = load_and_validate_task(path)
        if task is None:
            validation_errors[case_id] = errors
            continue
        if errors:
            validation_errors[case_id] = errors
            continue
        row = audit_hard_benchmark_task(task)
        row["path"] = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
        rows.append(row)

    boundary_ready_count = sum(1 for row in rows if bool(row.get("boundary_ready")))
    focus_counts: dict[str, int] = {}
    for row in rows:
        focus = str(row.get("benchmark_focus") or "")
        if focus:
            focus_counts[focus] = focus_counts.get(focus, 0) + 1

    status = (
        "PASS"
        if len(rows) == len(case_ids) and not validation_errors and boundary_ready_count == len(case_ids)
        else "REVIEW"
    )
    summary = {
        "version": "v0.32.0",
        "status": status,
        "analysis_scope": "hard_family_expansion",
        "task_root": str(task_root.relative_to(REPO_ROOT)) if task_root.is_relative_to(REPO_ROOT) else str(task_root),
        "case_ids": list(case_ids),
        "task_count": len(rows),
        "expected_task_count": len(case_ids),
        "boundary_ready_count": boundary_ready_count,
        "validation_error_count": len(validation_errors),
        "focus_counts": dict(sorted(focus_counts.items())),
        "decision": (
            "hard_family_expansion_ready_for_live_baseline"
            if status == "PASS"
            else "hard_family_expansion_needs_review"
        ),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary, rows=rows, validation_errors=validation_errors)
    return summary


def write_outputs(
    *,
    out_dir: Path,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    validation_errors: dict[str, list[str]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "task_audit.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "validation_errors.json").write_text(
        json.dumps(validation_errors, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
