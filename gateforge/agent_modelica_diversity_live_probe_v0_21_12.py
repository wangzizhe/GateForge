from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_candidate_diversity_v0_20_3 import analyze_round_diversity
from gateforge.agent_modelica_candidate_ranker_v1 import rank_candidates
from gateforge.agent_modelica_complex_single_root_pack_v0_21_8 import extract_model_name
from gateforge.agent_modelica_complex_single_root_repair_benchmark_v0_21_10 import load_jsonl
from gateforge.agent_modelica_diversity_resampling_v0_20_4 import build_safe_resampling_note
from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
from gateforge.experiment_runner_shared import (
    REPO_ROOT,
    run_check_and_simulate_omc,
    run_check_only_omc,
)


DEFAULT_BENCHMARK = REPO_ROOT / "artifacts" / "complex_single_root_repair_benchmark_v0_21_10" / "admitted_cases.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "diversity_live_probe_v0_21_12"

MODE_TO_CONTEXT = {
    "standard-c5": "",
    "diversity-c5": build_safe_resampling_note({"recommendation": "diversity_resample"}),
}


RepairFn = Callable[..., list[dict[str, Any]]]
CheckFn = Callable[[str, str], tuple[bool, str]]
SimulateFn = Callable[[str, str], tuple[bool, bool, str]]


def load_cases(path: Path = DEFAULT_BENCHMARK) -> list[dict[str, Any]]:
    return load_jsonl(path)


def read_case_model(case: dict[str, Any]) -> tuple[str, str]:
    model_path = Path(str(case.get("mutated_model_path") or ""))
    model_text = model_path.read_text(encoding="utf-8")
    model_name = extract_model_name(model_text)
    if not model_name:
        model_name = str(case.get("task_id") or case.get("candidate_id") or "")
    return model_text, model_name


def build_context_block(mode: str) -> tuple[str, str]:
    note = MODE_TO_CONTEXT.get(mode, "")
    if not note:
        return "", "Candidate generation profile"
    return (
        "Candidate generation profile:\n"
        "- Generate structurally distinct repair hypotheses.\n"
        "- Vary the declaration/equation edit shape across candidates.\n"
        "- Do not use hidden benchmark metadata, case identifiers, model family routing, or variable-name hints.\n"
        f"- Profile note: {note}",
        "Candidate diversity profile",
    )


def run_first_turn_probe(
    case: dict[str, Any],
    *,
    mode: str,
    repair_fn: RepairFn = llm_repair_model_text_multi,
    check_fn: CheckFn = run_check_only_omc,
    simulate_fn: SimulateFn = run_check_and_simulate_omc,
) -> dict[str, Any]:
    model_text, model_name = read_case_model(case)
    check_ok, omc_output = check_fn(model_text, model_name)
    context_block, context_label = build_context_block(mode)
    candidates = repair_fn(
        planner_backend=str(case.get("planner_backend") or os.getenv("LLM_PROVIDER") or "").strip(),
        original_text=model_text,
        failure_type=str(case.get("failure_type") or "model_check_error"),
        expected_stage=str(case.get("expected_stage") or "check"),
        error_excerpt=str(omc_output or "")[:12000],
        repair_actions=[],
        model_name=model_name,
        workflow_goal=str(case.get("workflow_goal") or ""),
        current_round=1,
        num_candidates=5,
        context_block=context_block,
        context_block_label=context_label,
    )

    def _runner(text: str) -> tuple[bool, str]:
        return check_fn(text, model_name)

    ranked = rank_candidates(candidates, run_omc=_runner)
    simulate_attempts: list[dict[str, Any]] = []
    for ranked_candidate in ranked:
        if not ranked_candidate.check_pass:
            break
        if not ranked_candidate.patched_text:
            continue
        chk, sim, _ = simulate_fn(ranked_candidate.patched_text, model_name)
        simulate_attempts.append(
            {
                "candidate_id": ranked_candidate.candidate_id,
                "temperature_used": ranked_candidate.temperature_used,
                "check_pass_again": bool(chk),
                "simulate_pass": bool(sim),
            }
        )

    round_row = {
        "round": 1,
        "num_candidates": 5,
        "ranked": [row.to_dict() for row in ranked],
        "simulate_attempts": simulate_attempts,
        "coverage_check_pass": sum(1 for row in ranked if row.check_pass),
        "any_check_pass": any(row.check_pass for row in ranked),
        "coverage_simulate_pass": sum(1 for row in simulate_attempts if row.get("simulate_pass")),
        "any_simulate_pass": any(row.get("simulate_pass") for row in simulate_attempts),
    }
    diversity = analyze_round_diversity(
        {"candidate_id": case.get("candidate_id"), "rounds": [round_row]},
        round_row,
    )
    return {
        "candidate_id": case.get("candidate_id"),
        "mutation_family": case.get("mutation_family"),
        "mode": mode,
        "initial_check_pass": bool(check_ok),
        "candidate_count": len(candidates),
        "context_profile_enabled": bool(context_block),
        "round": round_row,
        "diversity": diversity,
        "first_turn_any_check_pass": bool(round_row["any_check_pass"]),
        "first_turn_any_simulate_pass": bool(round_row["any_simulate_pass"]),
    }


def summarize_mode(mode: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    mode_rows = [row for row in rows if row.get("mode") == mode]
    count = len(mode_rows)
    any_check = sum(1 for row in mode_rows if row.get("first_turn_any_check_pass"))
    any_sim = sum(1 for row in mode_rows if row.get("first_turn_any_simulate_pass"))
    avg_structural = (
        sum(float((row.get("diversity") or {}).get("structural_uniqueness_rate") or 0.0) for row in mode_rows) / count
        if count
        else 0.0
    )
    avg_text = (
        sum(float((row.get("diversity") or {}).get("text_uniqueness_rate") or 0.0) for row in mode_rows) / count
        if count
        else 0.0
    )
    return {
        "mode": mode,
        "case_count": count,
        "first_turn_any_check_pass_count": any_check,
        "first_turn_any_check_pass_rate": any_check / count if count else 0.0,
        "first_turn_any_simulate_pass_count": any_sim,
        "first_turn_any_simulate_pass_rate": any_sim / count if count else 0.0,
        "average_structural_uniqueness_rate": avg_structural,
        "average_text_uniqueness_rate": avg_text,
    }


def build_ab_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    standard = summarize_mode("standard-c5", rows)
    diversity = summarize_mode("diversity-c5", rows)
    structural_delta = (
        diversity["average_structural_uniqueness_rate"] - standard["average_structural_uniqueness_rate"]
    )
    check_delta = (
        diversity["first_turn_any_check_pass_rate"] - standard["first_turn_any_check_pass_rate"]
    )
    simulate_delta = (
        diversity["first_turn_any_simulate_pass_rate"] - standard["first_turn_any_simulate_pass_rate"]
    )
    if diversity["case_count"] == 0 or standard["case_count"] == 0:
        conclusion = "diversity_live_probe_incomplete"
    elif structural_delta > 0.1 and (check_delta > 0.0 or simulate_delta > 0.0):
        conclusion = "diversity_profile_changed_candidates_and_improved_first_turn_signal"
    elif structural_delta > 0.1:
        conclusion = "diversity_profile_changed_candidates_without_first_turn_gain"
    else:
        conclusion = "diversity_profile_did_not_materially_change_candidate_structure"
    return {
        "version": "v0.21.12",
        "status": "PASS" if rows else "REVIEW",
        "analysis_mode": "first_turn_live_candidate_generation_ab",
        "discipline": "no_deterministic_repair_no_routing_no_hidden_hint",
        "mode_summaries": {
            "standard-c5": standard,
            "diversity-c5": diversity,
        },
        "deltas": {
            "structural_uniqueness_delta": structural_delta,
            "first_turn_any_check_pass_rate_delta": check_delta,
            "first_turn_any_simulate_pass_rate_delta": simulate_delta,
        },
        "conclusion": conclusion,
        "next_action": (
            "run_full_multiturn_diversity_arm"
            if conclusion == "diversity_profile_changed_candidates_and_improved_first_turn_signal"
            else "prefer_measurement_family_expansion_or_mutation_redesign"
        ),
    }


def run_diversity_live_probe(
    *,
    benchmark_path: Path = DEFAULT_BENCHMARK,
    out_dir: Path = DEFAULT_OUT_DIR,
    modes: list[str] | None = None,
    limit: int | None = None,
    repair_fn: RepairFn = llm_repair_model_text_multi,
    check_fn: CheckFn = run_check_only_omc,
    simulate_fn: SimulateFn = run_check_and_simulate_omc,
) -> dict[str, Any]:
    selected_modes = modes or ["standard-c5", "diversity-c5"]
    cases = load_cases(benchmark_path)
    if limit is not None:
        cases = cases[: max(0, int(limit))]
    rows: list[dict[str, Any]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for mode in selected_modes:
        for case in cases:
            row = run_first_turn_probe(
                case,
                mode=mode,
                repair_fn=repair_fn,
                check_fn=check_fn,
                simulate_fn=simulate_fn,
            )
            rows.append(row)
            write_outputs(out_dir=out_dir, rows=rows, summary=build_ab_summary(rows))
    summary = build_ab_summary(rows)
    write_outputs(out_dir=out_dir, rows=rows, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "probe_rows.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
