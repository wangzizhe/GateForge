from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from .agent_modelica_generation_audit_v0_19_60 import (
    build_generation_audit_summary,
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
from .llm_provider_adapter import resolve_provider_adapter


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "model_comparison_v0_19_64"

DEFAULT_MODEL_PROFILES = (
    "gemini_flash_lite:gemini:gemini-2.5-flash-lite",
    "anthropic_sonnet:anthropic:claude-sonnet-4-5",
)


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    provider_backend: str
    model: str


def parse_model_profiles(value: str | list[str] | tuple[str, ...] | None) -> list[ModelProfile]:
    raw_items: list[str]
    if value is None or value == "":
        raw_items = list(DEFAULT_MODEL_PROFILES)
    elif isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",") if item.strip()]
    else:
        raw_items = [str(item).strip() for item in value if str(item).strip()]
    profiles: list[ModelProfile] = []
    for item in raw_items:
        parts = item.split(":", 2)
        if len(parts) != 3 or not all(part.strip() for part in parts):
            raise ValueError(f"Invalid model profile spec: {item}")
        profile_id, provider_backend, model = [part.strip() for part in parts]
        profiles.append(ModelProfile(profile_id=profile_id, provider_backend=provider_backend, model=model))
    return profiles


@contextmanager
def temporary_model_env(profile: ModelProfile) -> Iterator[None]:
    keys = [
        "LLM_PROVIDER",
        "LLM_MODEL",
        "GATEFORGE_LIVE_PLANNER_BACKEND",
        "GATEFORGE_GEMINI_MODEL",
        "GEMINI_MODEL",
        "ANTHROPIC_MODEL",
        "OPENAI_MODEL",
        "MINIMAX_MODEL",
        "QWEN_MODEL",
    ]
    old = {key: os.environ.get(key) for key in keys}
    try:
        os.environ["LLM_PROVIDER"] = profile.provider_backend
        os.environ["LLM_MODEL"] = profile.model
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def check_profile_available(profile: ModelProfile) -> tuple[bool, str]:
    try:
        with temporary_model_env(profile):
            resolve_provider_adapter(profile.provider_backend)
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"
    return True, ""


def select_stratified_tasks(
    *,
    pool_dir: Path = DEFAULT_NL_TASK_POOL_DIR,
    task_id: str = "",
    max_tasks: int = 6,
) -> list[dict[str, Any]]:
    tasks = select_tasks(pool_dir=pool_dir, task_id=task_id, max_tasks=0)
    if task_id:
        return tasks[:1]
    if max_tasks <= 0:
        return tasks
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for difficulty in ("T1", "T2", "T3", "T4", "T5"):
        for task in tasks:
            task_id_value = str(task.get("task_id") or "")
            if task_id_value in seen_ids:
                continue
            if str(task.get("difficulty") or "") == difficulty:
                selected.append(task)
                seen_ids.add(task_id_value)
                break
    for task in tasks:
        if len(selected) >= max_tasks:
            break
        task_id_value = str(task.get("task_id") or "")
        if task_id_value not in seen_ids:
            selected.append(task)
            seen_ids.add(task_id_value)
    return selected[:max_tasks]


def build_generation_fn_for_profile(
    *,
    profile: ModelProfile,
    dry_run_fixture: bool,
    temperature: float = 0.2,
) -> Callable[[dict[str, Any]], tuple[str, str, str]]:
    if dry_run_fixture:
        return lambda task: fixture_generation_response_for_profile(task, profile)

    def _generate(task: dict[str, Any]) -> tuple[str, str, str]:
        with temporary_model_env(profile):
            return request_generation_from_llm(
                task=task,
                planner_backend=profile.provider_backend,
                temperature=temperature,
            )

    return _generate


def fixture_generation_response_for_profile(
    task: dict[str, Any],
    profile: ModelProfile,
) -> tuple[str, str, str]:
    if profile.provider_backend == "anthropic":
        task_id = str(task.get("task_id") or "")
        if task_id.endswith("thermal_lumped_wall") or task_id.endswith("fluid_tank_outflow"):
            safe_name = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in task_id)
            return (
                json.dumps(
                    {
                        "model_text": (
                            f"model {safe_name}\n"
                            "  parameter Real k = 1;\n"
                            "  Real x(start = 1);\n"
                            "equation\n"
                            "  der(x) = -k * x;\n"
                            "  annotation(experiment(StartTime=0, StopTime=1));\n"
                            f"end {safe_name};"
                        ),
                        "rationale": "fixture anthropic pass model",
                    }
                ),
                "",
                "fixture_anthropic",
            )
    return fixture_generation_response(task)


def run_model_profile(
    *,
    profile: ModelProfile,
    tasks: list[dict[str, Any]],
    dry_run_fixture: bool = False,
    evaluator_fn: Callable[[str, str], tuple[bool, bool, str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generation_fn = build_generation_fn_for_profile(profile=profile, dry_run_fixture=dry_run_fixture)
    evaluator_fn = evaluator_fn or (fixture_evaluate_model if dry_run_fixture else evaluate_model_with_omc)
    results = [
        {
            **run_generation_task(
                task,
                planner_backend=profile.provider_backend,
                generation_fn=generation_fn,
                evaluator_fn=evaluator_fn,
            ),
            "model_profile_id": profile.profile_id,
            "provider_backend": profile.provider_backend,
            "model": profile.model,
        }
        for task in tasks
    ]
    summary = build_generation_audit_summary(
        task_results=results,
        mutation_distribution=load_mutation_distribution(),
        mapping_statuses=parse_mapping_statuses(),
        dry_run_fixture=dry_run_fixture,
        planner_backend=profile.provider_backend,
    )
    summary.update(
        {
            "version": "v0.19.64",
            "model_profile_id": profile.profile_id,
            "provider_backend": profile.provider_backend,
            "model": profile.model,
            "task_ids": [str(task.get("task_id") or "") for task in tasks],
        }
    )
    return results, summary


def build_model_comparison_summary(
    *,
    profile_summaries: dict[str, dict[str, Any]],
    blocked_profiles: list[dict[str, Any]],
    dry_run_fixture: bool,
    task_ids: list[str],
) -> dict[str, Any]:
    completed = list(profile_summaries)
    sonnet_or_opus_completed = [
        profile_id
        for profile_id, summary in profile_summaries.items()
        if "sonnet" in str(summary.get("model") or "").lower()
        or "opus" in str(summary.get("model") or "").lower()
    ]
    comparisons: dict[str, dict[str, Any]] = {}
    for profile_id, summary in profile_summaries.items():
        comparisons[profile_id] = {
            "provider_backend": summary.get("provider_backend"),
            "model": summary.get("model"),
            "task_count": summary.get("task_count"),
            "pass_rate": summary.get("pass_rate"),
            "d_pq_total_variation": summary.get("d_pq_total_variation"),
            "bucket_counts": summary.get("bucket_counts"),
        }
    complete_success = len(completed) >= 2 and bool(sonnet_or_opus_completed)
    return {
        "version": "v0.19.64",
        "status": "DRY_RUN" if dry_run_fixture else ("PASS" if complete_success else "PARTIAL"),
        "dry_run_fixture": bool(dry_run_fixture),
        "task_count": len(task_ids),
        "task_ids": task_ids,
        "completed_profiles": completed,
        "blocked_profiles": blocked_profiles,
        "blocked_profile_count": len(blocked_profiles),
        "sonnet_or_opus_completed_profiles": sonnet_or_opus_completed,
        "profile_summaries": profile_summaries,
        "comparisons": comparisons,
        "success_criterion_met": complete_success,
        "conclusion": (
            "multi_model_generation_distribution_comparison_complete"
            if complete_success
            else "multi_model_comparison_infra_ready_but_model_agnostic_milestone_incomplete"
        ),
    }


def run_model_comparison(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    pool_dir: Path = DEFAULT_NL_TASK_POOL_DIR,
    model_profiles: str | list[str] | tuple[str, ...] | None = None,
    task_id: str = "",
    max_tasks: int = 6,
    dry_run_fixture: bool = False,
    evaluator_fn: Callable[[str, str], tuple[bool, bool, str]] | None = None,
) -> dict[str, Any]:
    profiles = parse_model_profiles(model_profiles)
    tasks = select_stratified_tasks(pool_dir=pool_dir, task_id=task_id, max_tasks=max_tasks)
    profile_results: dict[str, list[dict[str, Any]]] = {}
    profile_summaries: dict[str, dict[str, Any]] = {}
    blocked_profiles: list[dict[str, Any]] = []
    for profile in profiles:
        available, blocker = (True, "") if dry_run_fixture else check_profile_available(profile)
        if not available:
            blocked_profiles.append(
                {
                    "model_profile_id": profile.profile_id,
                    "provider_backend": profile.provider_backend,
                    "model": profile.model,
                    "blocker": blocker,
                }
            )
            continue
        results, summary = run_model_profile(
            profile=profile,
            tasks=tasks,
            dry_run_fixture=dry_run_fixture,
            evaluator_fn=evaluator_fn,
        )
        profile_results[profile.profile_id] = results
        profile_summaries[profile.profile_id] = summary
    summary = build_model_comparison_summary(
        profile_summaries=profile_summaries,
        blocked_profiles=blocked_profiles,
        dry_run_fixture=dry_run_fixture,
        task_ids=[str(task.get("task_id") or "") for task in tasks],
    )
    write_model_comparison_outputs(out_dir=out_dir, profile_results=profile_results, summary=summary)
    return summary


def write_model_comparison_outputs(
    *,
    out_dir: Path,
    profile_results: dict[str, list[dict[str, Any]]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_root = out_dir / "profiles"
    profile_root.mkdir(parents=True, exist_ok=True)
    for profile_id, results in profile_results.items():
        profile_summary = (summary.get("profile_summaries") or {}).get(profile_id) or {}
        write_generation_audit_outputs(
            out_dir=profile_root / profile_id,
            task_results=results,
            summary=profile_summary,
        )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "REPORT.md").write_text(render_model_comparison_report(summary), encoding="utf-8")


def render_model_comparison_report(summary: dict[str, Any]) -> str:
    lines = [
        "# v0.19.64 Multi-Model Generation Comparison",
        "",
        f"- status: `{summary.get('status')}`",
        f"- dry_run_fixture: `{summary.get('dry_run_fixture')}`",
        f"- task_count: `{summary.get('task_count')}`",
        f"- success_criterion_met: `{summary.get('success_criterion_met')}`",
        "",
        "## Completed Profiles",
    ]
    comparisons = summary.get("comparisons") or {}
    if not comparisons:
        lines.append("- none")
    for profile_id, row in comparisons.items():
        lines.append(
            f"- `{profile_id}` `{row.get('model')}`: pass_rate=`{row.get('pass_rate')}`, "
            f"d(P,Q)=`{row.get('d_pq_total_variation')}`, buckets=`{row.get('bucket_counts')}`"
        )
    lines.extend(["", "## Blocked Profiles"])
    blocked = summary.get("blocked_profiles") or []
    if not blocked:
        lines.append("- none")
    for row in blocked:
        lines.append(
            f"- `{row.get('model_profile_id')}` `{row.get('model')}`: `{row.get('blocker')}`"
        )
    return "\n".join(lines) + "\n"

