from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_split_plan_v0_56_0 import DEFAULT_OUT_DIR as SPLIT_OUT_DIR
from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json
from .agent_modelica_medium_candidate_admission_v0_55_0 import (
    DEFAULT_TASK_DIRS,
    DEFAULT_TASK_JSONL,
    FORBIDDEN_TASK_FIELDS,
    load_task_records,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPLIT = SPLIT_OUT_DIR / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_external_bundle_v0_57_0"

VISIBLE_FIELDS = (
    "case_id",
    "title",
    "description",
    "constraints",
    "initial_model",
    "verification",
    "task_type",
)


def build_external_task(task: dict[str, Any], *, split: str) -> dict[str, Any]:
    out = {field: task[field] for field in VISIBLE_FIELDS if field in task}
    if "description" not in out and "visible_task_description" in task:
        out["description"] = task["visible_task_description"]
    out["dataset_split"] = split
    out["submission_format"] = "Return the final repaired Modelica model text."
    out["verification_command"] = "Run model check first, then simulation when model check succeeds."
    for field in FORBIDDEN_TASK_FIELDS:
        out.pop(field, None)
    return out


def build_benchmark_external_bundle(
    *,
    split_summary: dict[str, Any],
    tasks_by_case: dict[str, dict[str, Any]],
    version: str = "v0.57.0",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    split_case_ids = split_summary.get("split_case_ids") if isinstance(split_summary.get("split_case_ids"), dict) else {}
    bundle_tasks: list[dict[str, Any]] = []
    missing: list[str] = []
    leakage: list[str] = []
    for split in ("dev", "holdout"):
        for case_id in split_case_ids.get(split, []) or []:
            task = tasks_by_case.get(str(case_id))
            if not task:
                missing.append(str(case_id))
                continue
            external_task = build_external_task(task, split=split)
            for field in FORBIDDEN_TASK_FIELDS:
                if field in external_task:
                    leakage.append(f"{case_id}:{field}")
            bundle_tasks.append(external_task)
    gaps: list[str] = []
    if missing:
        gaps.append("missing_task_records")
    if leakage:
        gaps.append("forbidden_field_leakage")
    if not bundle_tasks:
        gaps.append("empty_external_bundle")
    summary = {
        "version": version,
        "analysis_scope": "benchmark_external_bundle",
        "status": "REVIEW" if gaps else "PASS",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "external_bundle_ready" if not gaps else "external_bundle_incomplete",
        "task_count": len(bundle_tasks),
        "dev_task_count": sum(1 for task in bundle_tasks if task.get("dataset_split") == "dev"),
        "holdout_task_count": sum(1 for task in bundle_tasks if task.get("dataset_split") == "holdout"),
        "missing_task_record_count": len(missing),
        "missing_task_case_ids": sorted(missing),
        "leakage_issue_count": len(leakage),
        "leakage_issues": sorted(leakage),
        "leakage_contract": {
            "contains_hidden_oracle": False,
            "contains_reference_repair": False,
            "contains_internal_artifacts": False,
        },
        "gaps": gaps,
    }
    return summary, sorted(bundle_tasks, key=lambda task: (str(task.get("dataset_split") or ""), str(task.get("case_id") or "")))


def write_benchmark_external_bundle_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "tasks.jsonl").open("w", encoding="utf-8") as fh:
        for task in tasks:
            fh.write(json.dumps(task, sort_keys=True) + "\n")


def run_benchmark_external_bundle(
    *,
    split_path: Path = DEFAULT_SPLIT,
    task_dirs: tuple[Path, ...] = DEFAULT_TASK_DIRS,
    task_jsonl_paths: tuple[Path, ...] = DEFAULT_TASK_JSONL,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, tasks = build_benchmark_external_bundle(
        split_summary=load_json(split_path),
        tasks_by_case=load_task_records(task_dirs=task_dirs, task_jsonl_paths=task_jsonl_paths),
    )
    write_benchmark_external_bundle_outputs(out_dir=out_dir, summary=summary, tasks=tasks)
    return summary
