from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from .agent_modelica_generation_audit_v0_19_60 import (
    build_generation_audit_summary,
    build_generation_prompt,
    evaluate_model_with_omc,
    fixture_evaluate_model,
    fixture_generation_response,
    load_mutation_distribution,
    parse_mapping_statuses,
    request_generation_from_llm,
    run_generation_task,
    select_tasks,
    write_generation_audit_outputs,
)
from .agent_modelica_generation_taxonomy_v0_19_59 import DEFAULT_NL_TASK_POOL_DIR


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "prompt_ab_v0_19_63"

BASELINE_FAMILY = "baseline_json_only"
STRUCTURED_TEMPLATE_FAMILY = "structured_template"
DEFAULT_PROMPT_FAMILIES = (BASELINE_FAMILY, STRUCTURED_TEMPLATE_FAMILY)
MATERIAL_D_PQ_SHIFT_THRESHOLD = 0.05


def build_prompt_for_family(task: dict[str, Any], prompt_family: str) -> str:
    family = str(prompt_family or "").strip()
    if family == BASELINE_FAMILY:
        return build_generation_prompt(task)
    if family == STRUCTURED_TEMPLATE_FAMILY:
        return (
            "You are generating a standalone Modelica model from a natural-language task.\n"
            "Return ONLY one JSON object with keys: model_text, rationale.\n"
            "Do not include markdown.\n"
            "Do not include taxonomy labels, mutation labels, repair hints, or benchmark internals.\n"
            "Use this output construction order inside model_text:\n"
            "1. Model declaration with a task-specific model name.\n"
            "2. Parameters with numeric defaults and units only when you know the correct unit syntax.\n"
            "3. State and algebraic variable declarations.\n"
            "4. Equations that close the model structurally.\n"
            "5. annotation(experiment(...)) when appropriate.\n"
            "Keep the model standalone; avoid references to unavailable external project classes.\n"
            f"task_id: {str(task.get('task_id') or '').strip()}\n"
            f"difficulty: {str(task.get('difficulty') or '').strip()}\n"
            f"domain: {str(task.get('domain') or '').strip()}\n"
            f"acceptance: {json.dumps(task.get('acceptance') or [], ensure_ascii=True)}\n"
            "Natural-language task:\n"
            f"{str(task.get('prompt') or '').strip()}\n"
        )
    raise ValueError(f"Unknown prompt family: {prompt_family}")


def parse_prompt_families(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None or value == "":
        return list(DEFAULT_PROMPT_FAMILIES)
    if isinstance(value, str):
        families = [part.strip() for part in value.split(",") if part.strip()]
    else:
        families = [str(part).strip() for part in value if str(part).strip()]
    unknown = [family for family in families if family not in DEFAULT_PROMPT_FAMILIES]
    if unknown:
        raise ValueError(f"Unknown prompt families: {', '.join(unknown)}")
    if BASELINE_FAMILY not in families:
        families.insert(0, BASELINE_FAMILY)
    return families


def request_generation_for_family(
    *,
    task: dict[str, Any],
    prompt_family: str,
    planner_backend: str,
    temperature: float = 0.2,
) -> tuple[str, str, str]:
    if prompt_family == BASELINE_FAMILY:
        return request_generation_from_llm(
            task=task,
            planner_backend=planner_backend,
            temperature=temperature,
        )

    from .agent_modelica_l2_plan_replan_engine_v1 import send_with_budget
    from .llm_provider_adapter import resolve_provider_adapter

    adapter, config = resolve_provider_adapter(planner_backend)
    if config.provider_name == "rule":
        return "", "rule_backend_selected", "rule"
    config.temperature = float(temperature)
    text, err = send_with_budget(adapter, build_prompt_for_family(task, prompt_family), config)
    return text, err, config.provider_name


def build_generation_fn_for_family(
    *,
    prompt_family: str,
    planner_backend: str,
    dry_run_fixture: bool,
    temperature: float = 0.2,
) -> Callable[[dict[str, Any]], tuple[str, str, str]]:
    if dry_run_fixture:
        return lambda task: fixture_generation_response_for_family(task, prompt_family)

    def _generate(task: dict[str, Any]) -> tuple[str, str, str]:
        return request_generation_for_family(
            task=task,
            prompt_family=prompt_family,
            planner_backend=planner_backend,
            temperature=temperature,
        )

    return _generate


def fixture_generation_response_for_family(
    task: dict[str, Any],
    prompt_family: str,
) -> tuple[str, str, str]:
    if prompt_family == BASELINE_FAMILY:
        return fixture_generation_response(task)
    task_id = str(task.get("task_id") or "")
    model_name = re.sub(r"[^A-Za-z0-9_]", "_", task_id)
    if task_id.endswith("thermal_lumped_wall") or task_id.endswith("electrical_rc_step"):
        return (
            json.dumps(
                {
                    "model_text": (
                        f"model {model_name}\n"
                        "  parameter Real k = 1;\n"
                        "  Real x(start = 1);\n"
                        "equation\n"
                        "  der(x) = -k * x;\n"
                        "  annotation(experiment(StartTime=0, StopTime=1));\n"
                        f"end {model_name};"
                    ),
                    "rationale": "fixture structured pass model",
                }
            ),
            "",
            "fixture",
        )
    return fixture_generation_response(task)


def run_prompt_family(
    *,
    prompt_family: str,
    tasks: list[dict[str, Any]],
    planner_backend: str,
    dry_run_fixture: bool = False,
    generation_fn: Callable[[dict[str, Any]], tuple[str, str, str]] | None = None,
    evaluator_fn: Callable[[str, str], tuple[bool, bool, str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generation_fn = generation_fn or build_generation_fn_for_family(
        prompt_family=prompt_family,
        planner_backend=planner_backend,
        dry_run_fixture=dry_run_fixture,
    )
    evaluator_fn = evaluator_fn or (fixture_evaluate_model if dry_run_fixture else evaluate_model_with_omc)
    results = [
        {
            **run_generation_task(
                task,
                planner_backend=planner_backend,
                generation_fn=generation_fn,
                evaluator_fn=evaluator_fn,
            ),
            "prompt_family": prompt_family,
        }
        for task in tasks
    ]
    summary = build_generation_audit_summary(
        task_results=results,
        mutation_distribution=load_mutation_distribution(),
        mapping_statuses=parse_mapping_statuses(),
        dry_run_fixture=dry_run_fixture,
        planner_backend=planner_backend,
    )
    summary.update(
        {
            "version": "v0.19.63",
            "prompt_family": prompt_family,
            "family_role": "baseline" if prompt_family == BASELINE_FAMILY else "treatment",
        }
    )
    return results, summary


def build_prompt_ab_summary(
    *,
    family_summaries: dict[str, dict[str, Any]],
    planner_backend: str,
    dry_run_fixture: bool,
    material_shift_threshold: float = MATERIAL_D_PQ_SHIFT_THRESHOLD,
) -> dict[str, Any]:
    baseline = family_summaries[BASELINE_FAMILY]
    baseline_d = float(baseline.get("d_pq_total_variation") or 0.0)
    baseline_pass_rate = float(baseline.get("pass_rate") or 0.0)
    comparisons: dict[str, dict[str, Any]] = {}
    material_shift_families: list[str] = []
    for family, summary in family_summaries.items():
        d_pq = float(summary.get("d_pq_total_variation") or 0.0)
        pass_rate = float(summary.get("pass_rate") or 0.0)
        delta_d = round(d_pq - baseline_d, 6)
        bucket_shift = build_bucket_shift(
            baseline.get("generation_failure_distribution_p") or {},
            summary.get("generation_failure_distribution_p") or {},
        )
        comparison = {
            "d_pq_total_variation": round(d_pq, 6),
            "delta_d_pq_vs_baseline": delta_d,
            "pass_rate": pass_rate,
            "delta_pass_rate_vs_baseline": round(pass_rate - baseline_pass_rate, 6),
            "bucket_shift_vs_baseline": bucket_shift,
            "material_distribution_shift": abs(delta_d) >= float(material_shift_threshold),
        }
        comparisons[family] = comparison
        if family != BASELINE_FAMILY and comparison["material_distribution_shift"]:
            material_shift_families.append(family)
    return {
        "version": "v0.19.63",
        "status": "DRY_RUN" if dry_run_fixture else "PASS",
        "planner_backend": planner_backend,
        "dry_run_fixture": bool(dry_run_fixture),
        "prompt_families": list(family_summaries),
        "baseline_prompt_family": BASELINE_FAMILY,
        "material_d_pq_shift_threshold": float(material_shift_threshold),
        "family_summaries": family_summaries,
        "comparisons": comparisons,
        "material_shift_families": material_shift_families,
        "success_criterion_met": bool(material_shift_families),
        "conclusion": (
            "prompt_family_changes_generation_failure_distribution"
            if material_shift_families
            else "no_material_prompt_family_distribution_shift"
        ),
    }


def build_bucket_shift(
    baseline_dist: dict[str, float],
    treatment_dist: dict[str, float],
) -> dict[str, float]:
    keys = sorted(set(baseline_dist) | set(treatment_dist))
    return {
        key: round(float(treatment_dist.get(key, 0.0)) - float(baseline_dist.get(key, 0.0)), 6)
        for key in keys
    }


def run_prompt_ab(
    *,
    planner_backend: str,
    out_dir: Path = DEFAULT_OUT_DIR,
    pool_dir: Path = DEFAULT_NL_TASK_POOL_DIR,
    prompt_families: str | list[str] | tuple[str, ...] | None = None,
    task_id: str = "",
    max_tasks: int = 0,
    dry_run_fixture: bool = False,
    evaluator_fn: Callable[[str, str], tuple[bool, bool, str]] | None = None,
) -> dict[str, Any]:
    families = parse_prompt_families(prompt_families)
    tasks = select_tasks(pool_dir=pool_dir, task_id=task_id, max_tasks=max_tasks)
    family_results: dict[str, list[dict[str, Any]]] = {}
    family_summaries: dict[str, dict[str, Any]] = {}
    for family in families:
        results, summary = run_prompt_family(
            prompt_family=family,
            tasks=tasks,
            planner_backend=planner_backend,
            dry_run_fixture=dry_run_fixture,
            evaluator_fn=evaluator_fn,
        )
        family_results[family] = results
        family_summaries[family] = summary
    summary = build_prompt_ab_summary(
        family_summaries=family_summaries,
        planner_backend=planner_backend,
        dry_run_fixture=dry_run_fixture,
    )
    write_prompt_ab_outputs(out_dir=out_dir, family_results=family_results, summary=summary)
    return summary


def write_prompt_ab_outputs(
    *,
    out_dir: Path,
    family_results: dict[str, list[dict[str, Any]]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    family_root = out_dir / "families"
    family_root.mkdir(parents=True, exist_ok=True)
    for family, results in family_results.items():
        family_summary = (summary.get("family_summaries") or {}).get(family) or {}
        write_generation_audit_outputs(
            out_dir=family_root / family,
            task_results=results,
            summary=family_summary,
        )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "REPORT.md").write_text(render_prompt_ab_report(summary), encoding="utf-8")


def render_prompt_ab_report(summary: dict[str, Any]) -> str:
    lines = [
        "# v0.19.63 Prompt Family A/B",
        "",
        f"- status: `{summary.get('status')}`",
        f"- dry_run_fixture: `{summary.get('dry_run_fixture')}`",
        f"- prompt_families: `{', '.join(summary.get('prompt_families') or [])}`",
        f"- baseline_prompt_family: `{summary.get('baseline_prompt_family')}`",
        f"- success_criterion_met: `{summary.get('success_criterion_met')}`",
        "",
        "## Family Comparison",
    ]
    comparisons = summary.get("comparisons") or {}
    for family, row in comparisons.items():
        lines.append(
            f"- `{family}`: d(P,Q)=`{row.get('d_pq_total_variation')}`, "
            f"delta_d=`{row.get('delta_d_pq_vs_baseline')}`, "
            f"pass_rate=`{row.get('pass_rate')}`"
        )
    lines.extend(["", "## Material Shift Families"])
    material = summary.get("material_shift_families") or []
    if not material:
        lines.append("- none")
    for family in material:
        lines.append(f"- `{family}`")
    return "\n".join(lines) + "\n"
