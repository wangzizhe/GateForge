from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json, load_jsonl
from .agent_modelica_medium_candidate_admission_v0_55_0 import DEFAULT_TASK_DIRS, DEFAULT_TASK_JSONL, load_task_records


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MISSING = REPO_ROOT / "artifacts" / "positive_source_harvest_v0_59_0" / "missing_positive_source_case_ids.txt"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_positive_workbench_v0_60_0"


def load_missing_case_ids(path: Path = DEFAULT_MISSING) -> list[str]:
    if not path.exists():
        return []
    return sorted(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _latest_failure_for_case(case_id: str, artifact_root: Path) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    for path in sorted(artifact_root.glob("*/results.jsonl")):
        for row in load_jsonl(path):
            if str(row.get("case_id") or "") != case_id:
                continue
            if str(row.get("provider_error") or "").strip():
                continue
            if str(row.get("final_verdict") or "").upper() == "PASS":
                continue
            latest = {
                "source_result_path": str(path),
                "final_verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "tool_profile": str(row.get("tool_profile") or ""),
                "step_count": int(row.get("step_count") or 0),
                "final_model_text_present": bool(str(row.get("final_model_text") or "").strip()),
            }
    return latest


def infer_reference_strategy(case_id: str) -> str:
    if "adapter" in case_id or "cross_node" in case_id:
        return "adapter_contract_reference_repair_required"
    if "probe_bus" in case_id or "repl_array_flow" in case_id or "connector_bus" in case_id:
        return "probe_flow_ownership_reference_repair_required"
    return "manual_modelica_semantic_reference_repair_required"


def build_hard_positive_workbench(
    *,
    missing_case_ids: list[str],
    tasks_by_case: dict[str, dict[str, Any]],
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    version: str = "v0.60.0",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for case_id in sorted(missing_case_ids):
        task = tasks_by_case.get(case_id, {})
        latest_failure = _latest_failure_for_case(case_id, artifact_root)
        rows.append(
            {
                "case_id": case_id,
                "task_record_present": bool(task),
                "task_source_path": str(task.get("_source_path") or ""),
                "source_backed": bool(task.get("source_backed")),
                "model_check_first": bool((task.get("verification") or {}).get("check_model")) if isinstance(task.get("verification"), dict) else False,
                "has_initial_model": bool(str(task.get("initial_model") or "").strip()),
                "reference_status": "missing_verified_reference",
                "reference_strategy": infer_reference_strategy(case_id),
                "latest_failure": latest_failure,
                "prompt_visible": False,
                "wrapper_repair_allowed": False,
            }
        )
    complete_task_rows = [
        row
        for row in rows
        if row["task_record_present"] and row["source_backed"] and row["model_check_first"] and row["has_initial_model"]
    ]
    return {
        "version": version,
        "analysis_scope": "hard_positive_workbench",
        "status": "PASS" if rows and len(complete_task_rows) == len(rows) else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "hard_positive_workbench_ready" if rows else "hard_positive_workbench_empty",
        "case_count": len(rows),
        "complete_task_record_count": len(complete_task_rows),
        "missing_task_record_count": len(rows) - len(complete_task_rows),
        "case_ids": [row["case_id"] for row in rows],
        "strategy_counts": {
            strategy: sum(1 for row in rows if row["reference_strategy"] == strategy)
            for strategy in sorted({row["reference_strategy"] for row in rows})
        },
        "results": rows,
        "scope_contract": {
            "reference_repairs_prompt_visible": False,
            "wrapper_repair_allowed": False,
            "auto_candidate_selection_allowed": False,
            "purpose": "hidden_positive_solvability_workbench",
        },
        "next_actions": [
            "validate_candidate_reference_repairs_with_omc",
            "promote_verified_repairs_to_private_reference_assets",
            "move_unresolved_cases_to_frontier_if_reference_repair_cannot_be_verified",
        ],
    }


def write_hard_positive_workbench_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "workbench_cases.jsonl").open("w", encoding="utf-8") as fh:
        for row in summary["results"]:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_hard_positive_workbench(
    *,
    missing_path: Path = DEFAULT_MISSING,
    task_dirs: tuple[Path, ...] = DEFAULT_TASK_DIRS,
    task_jsonl_paths: tuple[Path, ...] = DEFAULT_TASK_JSONL,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_hard_positive_workbench(
        missing_case_ids=load_missing_case_ids(missing_path),
        tasks_by_case=load_task_records(task_dirs=task_dirs, task_jsonl_paths=task_jsonl_paths),
        artifact_root=artifact_root,
    )
    write_hard_positive_workbench_outputs(out_dir=out_dir, summary=summary)
    return summary
