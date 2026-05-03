from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .agent_modelica_benchmark_behavioral_oracle_v0_29_3 import evaluate_benchmark_behavior
from .agent_modelica_boundary_tool_use_baseline_v0_29_2 import task_to_tool_use_case
from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json, load_jsonl
from .agent_modelica_tool_use_harness_v0_28_0 import run_tool_use_case


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS = REPO_ROOT / "artifacts" / "benchmark_external_bundle_v0_61_0" / "tasks.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "solvable_holdout_baseline_v0_61_2"

RunCaseFn = Callable[..., dict[str, Any]]


def load_holdout_tasks(path: Path = DEFAULT_TASKS) -> list[dict[str, Any]]:
    return sorted(
        [row for row in load_jsonl(path) if str(row.get("dataset_split") or "") == "holdout"],
        key=lambda row: str(row.get("case_id") or ""),
    )


def run_solvable_holdout_baseline(
    *,
    tasks_path: Path = DEFAULT_TASKS,
    out_dir: Path = DEFAULT_OUT_DIR,
    max_steps: int = 10,
    max_token_budget: int = 32000,
    planner_backend: str = "auto",
    tool_profile: str = "base",
    summary_version: str = "v0.61.2",
    run_case_fn: RunCaseFn = run_tool_use_case,
) -> dict[str, Any]:
    tasks = load_holdout_tasks(tasks_path)
    cases = [task_to_tool_use_case(task) for task in tasks]
    results = [
        run_case_fn(
            case,
            max_steps=max_steps,
            max_token_budget=max_token_budget,
            planner_backend=planner_backend,
            tool_profile=tool_profile,
        )
        for case in cases
    ]
    for result, task in zip(results, tasks):
        if result.get("final_verdict") == "PASS":
            behavioral = evaluate_benchmark_behavior(task, str(result.get("final_model_text") or ""))
            result["behavioral_eval"] = behavioral
            if not bool(behavioral.get("pass")):
                result["final_verdict"] = "FAILED_BEHAVIOR"
        else:
            result["behavioral_eval"] = {"pass": False, "reason": "skipped_after_structural_failure"}
    pass_count = sum(1 for row in results if row.get("final_verdict") == "PASS")
    provider_error_count = sum(1 for row in results if row.get("provider_error"))
    summary = {
        "version": summary_version,
        "analysis_scope": "solvable_holdout_baseline",
        "status": "PASS" if tasks else "REVIEW",
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(tasks and provider_error_count == 0),
        "artifact_complete": True,
        "run_mode": "tool_use",
        "tool_profile": tool_profile,
        "provider_backend": planner_backend,
        "case_count": len(tasks),
        "pass_count": pass_count,
        "fail_count": len(tasks) - pass_count,
        "provider_error_count": provider_error_count,
        "case_ids": [str(task.get("case_id") or "") for task in tasks],
        "pass_case_ids": [str(row.get("case_id") or "") for row in results if row.get("final_verdict") == "PASS"],
        "fail_case_ids": [str(row.get("case_id") or "") for row in results if row.get("final_verdict") != "PASS"],
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "frontier_cases_excluded": True,
            "near_miss_cases_excluded": True,
        },
    }
    write_solvable_holdout_baseline_outputs(out_dir=out_dir, summary=summary, results=results)
    return summary


def run_solvable_holdout_baseline_streaming(
    *,
    tasks_path: Path = DEFAULT_TASKS,
    out_dir: Path = DEFAULT_OUT_DIR,
    case_ids: list[str] | None = None,
    limit: int = 0,
    max_steps: int = 10,
    max_token_budget: int = 32000,
    planner_backend: str = "auto",
    tool_profile: str = "base",
    summary_version: str = "v0.61.3",
    run_case_fn: RunCaseFn = run_tool_use_case,
) -> dict[str, Any]:
    wanted = set(case_ids or [])
    tasks = load_holdout_tasks(tasks_path)
    if wanted:
        tasks = [task for task in tasks if str(task.get("case_id") or "") in wanted]
    if limit:
        tasks = tasks[: max(0, int(limit))]
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    results_path = out_dir / "results.jsonl"
    results_path.write_text("", encoding="utf-8")
    for task in tasks:
        case = task_to_tool_use_case(task)
        result = run_case_fn(
            case,
            max_steps=max_steps,
            max_token_budget=max_token_budget,
            planner_backend=planner_backend,
            tool_profile=tool_profile,
        )
        if result.get("final_verdict") == "PASS":
            behavioral = evaluate_benchmark_behavior(task, str(result.get("final_model_text") or ""))
            result["behavioral_eval"] = behavioral
            if not bool(behavioral.get("pass")):
                result["final_verdict"] = "FAILED_BEHAVIOR"
        else:
            result["behavioral_eval"] = {"pass": False, "reason": "skipped_after_structural_failure"}
        results.append(result)
        with results_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result, sort_keys=True) + "\n")
        summary = _build_summary(
            tasks=tasks,
            results=results,
            summary_version=summary_version,
            planner_backend=planner_backend,
            tool_profile=tool_profile,
            completed_case_count=len(results),
        )
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not tasks:
        summary = _build_summary(
            tasks=[],
            results=[],
            summary_version=summary_version,
            planner_backend=planner_backend,
            tool_profile=tool_profile,
            completed_case_count=0,
        )
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return load_summary(out_dir / "summary.json")


def _build_summary(
    *,
    tasks: list[dict[str, Any]],
    results: list[dict[str, Any]],
    summary_version: str,
    planner_backend: str,
    tool_profile: str,
    completed_case_count: int,
) -> dict[str, Any]:
    pass_count = sum(1 for row in results if row.get("final_verdict") == "PASS")
    provider_error_count = sum(1 for row in results if row.get("provider_error"))
    return {
        "version": summary_version,
        "analysis_scope": "solvable_holdout_baseline_streaming",
        "status": "PASS" if tasks else "REVIEW",
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(tasks and completed_case_count == len(tasks) and provider_error_count == 0),
        "artifact_complete": completed_case_count == len(tasks),
        "run_mode": "tool_use",
        "tool_profile": tool_profile,
        "provider_backend": planner_backend,
        "case_count": len(tasks),
        "completed_case_count": completed_case_count,
        "pass_count": pass_count,
        "fail_count": completed_case_count - pass_count,
        "provider_error_count": provider_error_count,
        "case_ids": [str(task.get("case_id") or "") for task in tasks],
        "completed_case_ids": [str(row.get("case_id") or "") for row in results],
        "pass_case_ids": [str(row.get("case_id") or "") for row in results if row.get("final_verdict") == "PASS"],
        "fail_case_ids": [str(row.get("case_id") or "") for row in results if row.get("final_verdict") != "PASS"],
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "frontier_cases_excluded": True,
            "near_miss_cases_excluded": True,
            "streaming_artifacts_enabled": True,
        },
    }


def load_summary(path: Path) -> dict[str, Any]:
    return load_json(path)


def write_solvable_holdout_baseline_outputs(
    *,
    out_dir: Path,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
