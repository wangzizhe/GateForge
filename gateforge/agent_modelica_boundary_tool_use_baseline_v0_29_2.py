from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_loader_v0_29_0 import load_and_validate_task
from .agent_modelica_benchmark_behavioral_oracle_v0_29_3 import evaluate_benchmark_behavior
from .agent_modelica_tool_use_harness_v0_28_0 import run_tool_use_case

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "boundary_tool_use_baseline_v0_29_2"


def _extract_model_name(model_text: str, fallback: str) -> str:
    match = re.search(r"^\s*model\s+([A-Za-z_][A-Za-z0-9_]*)", model_text, re.MULTILINE)
    return match.group(1) if match else fallback


def task_to_tool_use_case(task: dict[str, Any]) -> dict[str, Any]:
    model_text = str(task.get("initial_model") or "")
    case_id = str(task.get("case_id") or "")
    verification = task.get("verification") if isinstance(task.get("verification"), dict) else {}
    simulate = verification.get("simulate") if isinstance(verification.get("simulate"), dict) else {}
    return {
        "case_id": case_id,
        "model_name": _extract_model_name(model_text, case_id or "model"),
        "model_text": model_text,
        "workflow_goal": "\n".join(
            part
            for part in (
                str(task.get("description") or ""),
                "\n".join(str(item) for item in task.get("constraints") or []),
            )
            if part.strip()
        ),
        "task_type": str(task.get("task_type") or ""),
        "difficulty": str(task.get("difficulty") or ""),
        "final_stop_time": float(simulate.get("stop_time") or 0.05),
        "final_intervals": int(simulate.get("intervals") or 5),
        "external_context": str(task.get("external_context") or ""),
        "benchmark_task": task,
    }


def _attach_external_context(cases: list[dict[str, Any]], context_text: str) -> list[dict[str, Any]]:
    if not context_text.strip():
        return cases
    updated: list[dict[str, Any]] = []
    for case in cases:
        copy = dict(case)
        copy["external_context"] = context_text
        updated.append(copy)
    return updated


def load_boundary_cases(
    *,
    task_root: Path = DEFAULT_TASK_ROOT,
    case_id_prefix: str = "boundary_",
    case_ids: list[str] | None = None,
    external_context: str = "",
    limit: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    wanted = set(case_ids or [])
    if not task_root.exists():
        paths: list[Path] = []
    elif wanted:
        paths = sorted(task_root / f"{case_id}.json" for case_id in wanted)
    else:
        paths = sorted(task_root.glob(f"{case_id_prefix}*.json"))
    cases: list[dict[str, Any]] = []
    errors: dict[str, list[str]] = {}
    for path in paths:
        if wanted and not path.exists():
            errors[str(path)] = ["task_file_missing"]
            continue
        task, task_errors = load_and_validate_task(path)
        if task is None:
            errors[str(path)] = task_errors
            continue
        case_id = str(task.get("case_id") or path.stem)
        if wanted and case_id not in wanted:
            errors[case_id] = ["case_id_mismatch"]
            continue
        if task_errors:
            errors[case_id] = task_errors
            continue
        cases.append(task_to_tool_use_case(task))
        if limit and len(cases) >= max(0, int(limit)):
            break
    return cases, errors


def run_boundary_tool_use_baseline(
    *,
    task_root: Path = DEFAULT_TASK_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
    case_id_prefix: str = "boundary_",
    case_ids: list[str] | None = None,
    external_context: str = "",
    limit: int = 0,
    max_steps: int = 10,
    max_token_budget: int = 32000,
    planner_backend: str = "auto",
    tool_profile: str = "base",
    summary_version: str = "v0.29.4",
) -> dict[str, Any]:
    cases, load_errors = load_boundary_cases(
        task_root=task_root,
        case_id_prefix=case_id_prefix,
        case_ids=case_ids,
        limit=limit,
    )
    cases = _attach_external_context(cases, external_context)
    results = [
        run_tool_use_case(
            case,
            max_steps=max_steps,
            max_token_budget=max_token_budget,
            planner_backend=planner_backend,
            tool_profile=tool_profile,
        )
        for case in cases
    ]
    for result, case in zip(results, cases):
        task = case.get("benchmark_task") if isinstance(case.get("benchmark_task"), dict) else {}
        if result.get("final_verdict") == "PASS":
            behavioral = evaluate_benchmark_behavior(task, str(result.get("final_model_text") or ""))
            result["behavioral_eval"] = behavioral
            if not bool(behavioral.get("pass")):
                result["final_verdict"] = "FAILED_BEHAVIOR"
        else:
            result["behavioral_eval"] = {"pass": False, "reason": "skipped_after_structural_failure"}
    pass_count = sum(1 for row in results if row.get("final_verdict") == "PASS")
    behavioral_fail_count = sum(1 for row in results if row.get("final_verdict") == "FAILED_BEHAVIOR")
    provider_error_count = sum(1 for row in results if row.get("provider_error"))
    tool_call_counts: dict[str, int] = {}
    for row in results:
        for step in row.get("steps", []):
            for tool_call in step.get("tool_calls", []):
                name = str(tool_call.get("name") or "")
                if name:
                    tool_call_counts[name] = tool_call_counts.get(name, 0) + 1
    summary = {
        "version": summary_version,
        "status": "PASS" if cases and not load_errors else "REVIEW",
        "analysis_scope": "boundary_tool_use_baseline",
        "run_mode": "tool_use",
        "tool_profile": tool_profile,
        "provider_backend": planner_backend,
        "case_id_prefix": case_id_prefix,
        "case_ids": list(case_ids or []),
        "external_context_used": bool(external_context.strip()),
        "external_context_chars": len(external_context),
        "case_count": len(cases),
        "pass_count": pass_count,
        "fail_count": len(cases) - pass_count,
        "behavioral_fail_count": behavioral_fail_count,
        "provider_error_count": provider_error_count,
        "load_error_count": len(load_errors),
        "tool_call_counts": dict(sorted(tool_call_counts.items())),
        "decision": (
            "boundary_baseline_has_failures_for_tool_ablation"
            if cases and pass_count < len(cases)
            else "boundary_baseline_solved_current_candidates"
        ),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary, results=results, load_errors=load_errors)
    return summary


def write_outputs(
    *,
    out_dir: Path,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    load_errors: dict[str, list[str]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in results:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "load_errors.json").write_text(
        json.dumps(load_errors, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
