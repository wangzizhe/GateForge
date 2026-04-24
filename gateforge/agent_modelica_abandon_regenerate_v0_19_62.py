from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .agent_modelica_generation_audit_v0_19_60 import (
    DEFAULT_OUT_DIR as DEFAULT_V060_INPUT_DIR,
    build_generation_audit_summary,
    fixture_evaluate_model,
    fixture_generation_response,
    load_mutation_distribution,
    parse_mapping_statuses,
    request_generation_from_llm,
    run_generation_task,
    write_generation_audit_outputs,
)
from .agent_modelica_generation_taxonomy_v0_19_59 import (
    DEFAULT_NL_TASK_POOL_DIR,
    load_nl_tasks,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "abandon_regenerate_v0_19_62"

REPAIR_COST_BY_BUCKET = {
    "ET01": 3.0,
    "ET02": 3.0,
    "ET03": 2.0,
    "ET07": 1.0,
}


def load_baseline_task_results(input_dir: Path = DEFAULT_V060_INPUT_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((input_dir / "tasks").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def load_task_lookup(pool_dir: Path = DEFAULT_NL_TASK_POOL_DIR) -> dict[str, dict[str, Any]]:
    return {str(task.get("task_id") or ""): task for task in load_nl_tasks(pool_dir)}


def estimate_repair_cost(result: dict[str, Any]) -> float:
    bucket_id = str((result.get("classification") or {}).get("bucket_id") or "")
    if bucket_id == "PASS" or str(result.get("final_status") or "") == "pass":
        return 0.0
    return float(REPAIR_COST_BY_BUCKET.get(bucket_id, 2.0))


def should_abandon_and_regenerate(
    result: dict[str, Any],
    *,
    generation_cost: float = 1.0,
    repair_cost_multiplier: float = 1.5,
    no_improvement_rounds: int = 1,
    min_no_improvement_rounds: int = 1,
) -> bool:
    if str(result.get("final_status") or "") == "pass":
        return False
    repair_cost = estimate_repair_cost(result)
    return (
        repair_cost > float(repair_cost_multiplier) * float(generation_cost)
        and int(no_improvement_rounds) >= int(min_no_improvement_rounds)
    )


def build_regeneration_generation_fn(
    *,
    planner_backend: str,
    dry_run_fixture: bool,
    temperature: float = 0.8,
) -> Callable[[dict[str, Any]], tuple[str, str, str]]:
    if dry_run_fixture:
        return fixture_generation_response

    def _generate(task: dict[str, Any]) -> tuple[str, str, str]:
        return request_generation_from_llm(
            task=task,
            planner_backend=planner_backend,
            temperature=temperature,
        )

    return _generate


def run_abandon_regenerate(
    *,
    planner_backend: str,
    input_dir: Path = DEFAULT_V060_INPUT_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    pool_dir: Path = DEFAULT_NL_TASK_POOL_DIR,
    dry_run_fixture: bool = False,
    generation_cost: float = 1.0,
    repair_cost_multiplier: float = 1.5,
    min_no_improvement_rounds: int = 1,
    generation_fn: Callable[[dict[str, Any]], tuple[str, str, str]] | None = None,
    evaluator_fn: Callable[[str, str], tuple[bool, bool, str]] | None = None,
) -> dict[str, Any]:
    baseline_results = load_baseline_task_results(input_dir)
    task_lookup = load_task_lookup(pool_dir)
    generation_fn = generation_fn or build_regeneration_generation_fn(
        planner_backend=planner_backend,
        dry_run_fixture=dry_run_fixture,
    )
    if dry_run_fixture and evaluator_fn is None:
        evaluator_fn = fixture_evaluate_model

    final_results: list[dict[str, Any]] = []
    regeneration_results: list[dict[str, Any]] = []
    for baseline in baseline_results:
        should_regenerate = should_abandon_and_regenerate(
            baseline,
            generation_cost=generation_cost,
            repair_cost_multiplier=repair_cost_multiplier,
            no_improvement_rounds=1,
            min_no_improvement_rounds=min_no_improvement_rounds,
        )
        if not should_regenerate:
            row = dict(baseline)
            row["abandon_decision"] = "keep_initial_generation"
            row["regenerated"] = False
            final_results.append(row)
            continue
        task_id = str(baseline.get("task_id") or "")
        task = task_lookup.get(task_id)
        if not task:
            row = dict(baseline)
            row["abandon_decision"] = "regeneration_skipped_missing_task"
            row["regenerated"] = False
            final_results.append(row)
            continue
        regenerated = run_generation_task(
            task,
            planner_backend=planner_backend,
            generation_fn=generation_fn,
            evaluator_fn=evaluator_fn,
        )
        regenerated["abandon_decision"] = "regenerated_after_budget_gate"
        regenerated["regenerated"] = True
        regenerated["baseline_bucket_id"] = (baseline.get("classification") or {}).get("bucket_id")
        regenerated["baseline_final_status"] = baseline.get("final_status")
        regeneration_results.append(regenerated)
        final_results.append(regenerated)

    summary = build_abandon_regenerate_summary(
        baseline_results=baseline_results,
        final_results=final_results,
        regeneration_results=regeneration_results,
        planner_backend=planner_backend,
        dry_run_fixture=dry_run_fixture,
        generation_cost=generation_cost,
        repair_cost_multiplier=repair_cost_multiplier,
        min_no_improvement_rounds=min_no_improvement_rounds,
    )
    write_outputs(out_dir=out_dir, final_results=final_results, regeneration_results=regeneration_results, summary=summary)
    return summary


def _pass_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if str(row.get("final_status") or "") == "pass")


def build_abandon_regenerate_summary(
    *,
    baseline_results: list[dict[str, Any]],
    final_results: list[dict[str, Any]],
    regeneration_results: list[dict[str, Any]],
    planner_backend: str,
    dry_run_fixture: bool,
    generation_cost: float,
    repair_cost_multiplier: float,
    min_no_improvement_rounds: int,
) -> dict[str, Any]:
    baseline_passes = _pass_count(baseline_results)
    final_passes = _pass_count(final_results)
    regen_passes = _pass_count(regeneration_results)
    task_count = len(baseline_results)
    regeneration_rate = len(regeneration_results) / task_count if task_count else 0.0
    audit_summary = build_generation_audit_summary(
        task_results=final_results,
        mutation_distribution=load_mutation_distribution(),
        mapping_statuses=parse_mapping_statuses(),
        dry_run_fixture=dry_run_fixture,
        planner_backend=planner_backend,
    )
    return {
        "version": "v0.19.62",
        "status": "DRY_RUN" if dry_run_fixture else "PASS",
        "planner_backend": planner_backend,
        "dry_run_fixture": bool(dry_run_fixture),
        "task_count": task_count,
        "without_abandon_pass_count": baseline_passes,
        "without_abandon_pass_rate": baseline_passes / task_count if task_count else 0.0,
        "with_abandon_pass_count": final_passes,
        "with_abandon_pass_rate": final_passes / task_count if task_count else 0.0,
        "abandon_trigger_count": len(regeneration_results),
        "regeneration_rate": round(regeneration_rate, 6),
        "regeneration_pass_count": regen_passes,
        "regeneration_pass_rate": regen_passes / len(regeneration_results) if regeneration_results else 0.0,
        "generation_cost": float(generation_cost),
        "repair_cost_multiplier": float(repair_cost_multiplier),
        "min_no_improvement_rounds": int(min_no_improvement_rounds),
        "final_generation_failure_distribution_p": audit_summary.get("generation_failure_distribution_p", {}),
        "final_d_pq_total_variation": audit_summary.get("d_pq_total_variation"),
        "success_criterion_met": (
            (final_passes / task_count if task_count else 0.0)
            >= (baseline_passes / task_count if task_count else 0.0)
        ),
        "regenerated_task_ids": [str(row.get("task_id") or "") for row in regeneration_results],
        "conclusion": (
            "abandon_regenerate_non_degrading"
            if final_passes >= baseline_passes
            else "abandon_regenerate_degraded"
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# v0.19.62 Abandon-Regenerate",
        "",
        f"- status: `{summary.get('status')}`",
        f"- task_count: `{summary.get('task_count')}`",
        f"- without_abandon_pass_rate: `{summary.get('without_abandon_pass_rate')}`",
        f"- with_abandon_pass_rate: `{summary.get('with_abandon_pass_rate')}`",
        f"- abandon_trigger_count: `{summary.get('abandon_trigger_count')}`",
        f"- regeneration_rate: `{summary.get('regeneration_rate')}`",
        f"- regeneration_pass_rate: `{summary.get('regeneration_pass_rate')}`",
        f"- success_criterion_met: `{summary.get('success_criterion_met')}`",
        "",
        "## Regenerated Tasks",
    ]
    for task_id in summary.get("regenerated_task_ids") or []:
        lines.append(f"- `{task_id}`")
    return "\n".join(lines) + "\n"


def write_outputs(
    *,
    out_dir: Path,
    final_results: list[dict[str, Any]],
    regeneration_results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    write_generation_audit_outputs(out_dir=out_dir, task_results=final_results, summary={
        **summary,
        "task_results": [
            {
                "task_id": row.get("task_id"),
                "final_status": row.get("final_status"),
                "bucket_id": (row.get("classification") or {}).get("bucket_id"),
                "regenerated": row.get("regenerated"),
                "abandon_decision": row.get("abandon_decision"),
            }
            for row in final_results
        ],
    })
    (out_dir / "regeneration_attempts.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in regeneration_results),
        encoding="utf-8",
    )
    (out_dir / "REPORT.md").write_text(render_report(summary), encoding="utf-8")

