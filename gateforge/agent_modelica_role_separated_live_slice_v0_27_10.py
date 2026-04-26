from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .agent_modelica_deepseek_frozen_harness_baseline_v0_27_0 import (
    DEFAULT_OUT_DIR as V0270_OUT_DIR,
    CheckFn,
    RepairFn,
    llm_repair_model_text,
    run_live_case,
    run_omc_check,
)
from .agent_modelica_deepseek_source_backed_slice_v0_27_1 import (
    DEFAULT_V0226_CANDIDATES,
    DEFAULT_V0228_ADMITTED,
    _by_candidate_id,
    load_jsonl,
    write_outputs,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SLICE_PLAN = REPO_ROOT / "artifacts" / "benchmark_slice_plan_v0_27_9" / "slice_plan.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "role_separated_live_slice_v0_27_10"


def _infer_model_name_from_text(model_text: str, fallback: str) -> str:
    match = re.search(r"\bmodel\s+([A-Za-z_][A-Za-z0-9_]*)", model_text)
    if match:
        return match.group(1)
    return fallback


def _resolve_case_from_source_row(
    *,
    plan_row: dict[str, Any],
    source_row: dict[str, Any],
) -> dict[str, Any] | None:
    model_path = Path(str(source_row.get("target_model_path") or source_row.get("mutated_model_path") or ""))
    source_model_path = Path(str(source_row.get("source_model_path") or ""))
    if not model_path.exists() or not source_model_path.exists():
        return None
    model_text = model_path.read_text(encoding="utf-8")
    model_name = str(source_row.get("target_model_name") or source_row.get("source_model_name") or "")
    if not model_name:
        model_name = _infer_model_name_from_text(model_text, model_path.stem)
    return {
        "case_id": str(plan_row.get("candidate_id") or source_row.get("candidate_id") or ""),
        "model_name": model_name,
        "failure_type": str(source_row.get("failure_type") or source_row.get("target_bucket_id") or "model_check_error"),
        "workflow_goal": str(
            source_row.get("workflow_goal")
            or "Repair the source-backed Modelica mutation using only model text and compiler feedback."
        ),
        "model_text": model_text,
        "mutation_family": str(plan_row.get("family") or source_row.get("mutation_family") or source_row.get("mutation_pattern") or ""),
        "split": str(plan_row.get("split") or ""),
        "repeatability_class": str(plan_row.get("repeatability_class") or ""),
        "slice_role": str(plan_row.get("slice_role") or ""),
        "source_model_path": str(source_model_path),
        "mutated_model_path": str(model_path),
        "source_backed": True,
        "workflow_proximal": True,
    }


def resolve_role_separated_cases(
    *,
    slice_plan_path: Path = DEFAULT_SLICE_PLAN,
    v0226_candidates_path: Path = DEFAULT_V0226_CANDIDATES,
    v0228_admitted_path: Path = DEFAULT_V0228_ADMITTED,
    slice_role: str = "capability_baseline",
    limit: int = 2,
) -> list[dict[str, Any]]:
    plan_rows = [row for row in load_jsonl(slice_plan_path) if str(row.get("slice_role") or "") == slice_role]
    v0226 = _by_candidate_id(load_jsonl(v0226_candidates_path))
    v0228 = _by_candidate_id(load_jsonl(v0228_admitted_path))
    resolved: list[dict[str, Any]] = []
    for plan_row in plan_rows:
        candidate_id = str(plan_row.get("candidate_id") or "")
        source_row = v0226.get(candidate_id) or v0228.get(candidate_id)
        if not source_row:
            continue
        case = _resolve_case_from_source_row(plan_row=plan_row, source_row=source_row)
        if not case:
            continue
        resolved.append(case)
        if len(resolved) >= max(0, int(limit)):
            break
    return resolved


def run_role_separated_live_slice(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    slice_plan_path: Path = DEFAULT_SLICE_PLAN,
    v0226_candidates_path: Path = DEFAULT_V0226_CANDIDATES,
    v0228_admitted_path: Path = DEFAULT_V0228_ADMITTED,
    slice_role: str = "capability_baseline",
    limit: int = 2,
    max_rounds: int = 3,
    planner_backend: str = "auto",
    check_fn: CheckFn = run_omc_check,
    repair_fn: RepairFn = llm_repair_model_text,
) -> dict[str, Any]:
    cases = resolve_role_separated_cases(
        slice_plan_path=slice_plan_path,
        v0226_candidates_path=v0226_candidates_path,
        v0228_admitted_path=v0228_admitted_path,
        slice_role=slice_role,
        limit=limit,
    )
    results = [
        run_live_case(
            case,
            max_rounds=max_rounds,
            planner_backend=planner_backend,
            check_fn=check_fn,
            repair_fn=repair_fn,
        )
        for case in cases
    ]
    pass_count = sum(1 for row in results if row.get("final_verdict") == "PASS")
    provider_errors = sum(1 for row in results if any(str(a.get("llm_error") or "") for a in row.get("attempts", [])))
    observation_error_count = sum(int(row.get("observation_validation_error_count") or 0) for row in results)
    true_multi_turn_count = sum(1 for row in results if row.get("true_multi_turn"))
    mixed_pass_rate_allowed = slice_role == "capability_baseline"
    summary = {
        "version": "v0.27.10",
        "status": "PASS" if cases and observation_error_count == 0 else "REVIEW",
        "analysis_scope": "role_separated_live_slice",
        "slice_role": slice_role,
        "slice_plan_artifact": str(DEFAULT_SLICE_PLAN.relative_to(REPO_ROOT)),
        "upstream_frozen_harness": str(V0270_OUT_DIR.relative_to(REPO_ROOT)),
        "provider": "deepseek",
        "model_profile": "deepseek-v4-flash",
        "run_mode": "raw_only",
        "max_rounds": int(max_rounds),
        "case_count": len(results),
        "pass_count": pass_count,
        "provider_error_count": provider_errors,
        "observation_validation_error_count": observation_error_count,
        "true_multi_turn_count": true_multi_turn_count,
        "mixed_pass_rate_allowed": mixed_pass_rate_allowed,
        "selected_case_ids": [str(case.get("case_id") or "") for case in cases],
        "selected_families": sorted({str(case.get("mutation_family") or "") for case in cases}),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": (
            "role_separated_live_slice_ready"
            if cases and observation_error_count == 0
            else "role_separated_live_slice_needs_review"
        ),
        "next_focus": "review_capability_slice_before_running_diagnostic_or_hard_negative",
    }
    write_outputs(out_dir=out_dir, summary=summary, results=results)
    return summary
