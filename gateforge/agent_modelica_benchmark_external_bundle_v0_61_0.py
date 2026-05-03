from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_external_bundle_v0_57_0 import (
    build_benchmark_external_bundle,
    write_benchmark_external_bundle_outputs,
)
from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json
from .agent_modelica_medium_candidate_admission_v0_55_0 import DEFAULT_TASK_DIRS, DEFAULT_TASK_JSONL, load_task_records


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPLIT = REPO_ROOT / "artifacts" / "benchmark_split_rebuild_v0_60_3" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_external_bundle_v0_61_0"


def build_freeze_ready_external_bundle(
    *,
    split_summary: dict[str, Any],
    tasks_by_case: dict[str, dict[str, Any]],
    version: str = "v0.61.0",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary, tasks = build_benchmark_external_bundle(
        split_summary=split_summary,
        tasks_by_case=tasks_by_case,
        version=version,
    )
    summary = dict(summary)
    summary["analysis_scope"] = "benchmark_external_bundle_freeze_ready"
    summary["source_split"] = "benchmark_split_rebuild_v0_60_3"
    summary["bundle_scope"] = "solvable_dev_holdout_only"
    summary["frontier_excluded_from_bundle"] = True
    summary["near_miss_excluded_from_bundle"] = True
    summary["readiness_status"] = (
        "freeze_ready_external_bundle_ready" if summary["status"] == "PASS" else "freeze_ready_external_bundle_incomplete"
    )
    return summary, tasks


def run_freeze_ready_external_bundle(
    *,
    split_path: Path = DEFAULT_SPLIT,
    task_dirs: tuple[Path, ...] = DEFAULT_TASK_DIRS,
    task_jsonl_paths: tuple[Path, ...] = DEFAULT_TASK_JSONL,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, tasks = build_freeze_ready_external_bundle(
        split_summary=load_json(split_path),
        tasks_by_case=load_task_records(task_dirs=task_dirs, task_jsonl_paths=task_jsonl_paths),
    )
    write_benchmark_external_bundle_outputs(out_dir=out_dir, summary=summary, tasks=tasks)
    return summary
