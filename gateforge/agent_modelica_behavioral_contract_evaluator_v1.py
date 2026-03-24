"""Behavioral Contract Evaluator — pure evaluation functions for v1.

Extracted from agent_modelica_live_executor_gemini_v1.py using the
Pure Evaluation Extraction Pattern. All functions are stateless and
deterministic; no Docker/LLM/OMC calls.

Dependency hierarchy (no cycles):
  agent_modelica_behavioral_contract_evaluator_v1
    -> agent_modelica_stage_branch_controller_v1 (L3)
"""
from __future__ import annotations

import re

from .agent_modelica_stage_branch_controller_v1 import (
    behavioral_contract_bucket,
    build_branching_stage_2_eval,
    build_multistep_eval,
)

BEHAVIORAL_MARKER_PREFIX = "gateforge_behavioral_contract_violation"
BEHAVIORAL_ROBUSTNESS_MARKER_PREFIX = "gateforge_behavioral_robustness_violation"


def normalize_behavioral_contract_text(text: str) -> str:
    rows: list[str] = []
    for line in str(text or "").splitlines():
        lowered = line.strip().lower()
        if lowered.startswith(f"// {BEHAVIORAL_MARKER_PREFIX}".lower()):
            continue
        if lowered.startswith(f"// {BEHAVIORAL_ROBUSTNESS_MARKER_PREFIX}".lower()):
            continue
        rows.append(" ".join(line.split()))
    return "\n".join([row for row in rows if row])

def evaluate_behavioral_contract_from_model_text(*, current_text: str, source_model_text: str, failure_type: str) -> dict | None:
    declared = str(failure_type or "").strip().lower()
    if declared not in {
        "steady_state_target_violation",
        "transient_response_contract_violation",
        "mode_transition_contract_violation",
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
        "stability_then_behavior",
        "behavior_then_robustness",
        "switch_then_recovery",
    }:
        return None
    passed = normalize_behavioral_contract_text(current_text) == normalize_behavioral_contract_text(source_model_text)
    bucket = behavioral_contract_bucket(declared)
    scenario_results = None
    if declared in {
        "param_perturbation_robustness_violation",
        "initial_condition_robustness_violation",
        "scenario_switch_robustness_violation",
    }:
        if passed:
            scenario_results = [
                {"scenario_id": "nominal", "pass": True},
                {"scenario_id": "neighbor_a", "pass": True},
                {"scenario_id": "neighbor_b", "pass": True},
            ]
        else:
            scenario_results = [
                {"scenario_id": "nominal", "pass": True},
                {"scenario_id": "neighbor_a", "pass": False},
                {"scenario_id": "neighbor_b", "pass": False},
            ]
    elif declared == "stability_then_behavior":
        lower_current = str(current_text or "").lower()
        if "model plantb" in lower_current:
            if re.search(r"height\s*=\s*(?:1\.2|1\.26)\b", current_text or "") and re.search(r"duration\s*=\s*(?:1\.1|1\.35)\b", current_text or ""):
                return build_multistep_eval(
                    stage="stage_1",
                    transition_reason="stability_constraints_still_violated",
                    transition_seen=False,
                    pass_all=False,
                    bucket="stability_margin_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"startTime\s*=\s*(?:0\.8|0\.92)\b", current_text or ""):
                if re.search(r"duration\s*=\s*0\.5\b", current_text or "") or re.search(r"height\s*=\s*1\b", current_text or ""):
                    return build_branching_stage_2_eval(
                        branch="neighbor_overfit_trap",
                        preferred_branch="behavior_timing_branch",
                        trap_branch=True,
                        branch_reason="duration_reset_too_early_before_timing_repair",
                        transition_reason="stability_restored_wrong_branch_exposed",
                        bucket="single_case_only",
                    )
                return build_branching_stage_2_eval(
                    branch="behavior_timing_branch",
                    preferred_branch="behavior_timing_branch",
                    trap_branch=False,
                    branch_reason="timing_gate_exposed_after_partial_stability_fix",
                    transition_reason="stability_restored_behavior_gate_exposed",
                    bucket="behavior_contract_miss",
                )
            else:
                return build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif "model switcha" in lower_current:
            if re.search(r"\bk\s*=\s*(?:1\.18|1\.24)\b", current_text or ""):
                return build_multistep_eval(
                    stage="stage_1",
                    transition_reason="stability_constraints_still_violated",
                    transition_seen=False,
                    pass_all=False,
                    bucket="stability_margin_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"width\s*=\s*(?:62|68)\b", current_text or "") or re.search(r"period\s*=\s*(?:0\.85|1\.05)\b", current_text or ""):
                trap = re.search(r"width\s*=\s*40\b", current_text or "") or re.search(r"period\s*=\s*0\.5\b", current_text or "")
                return build_branching_stage_2_eval(
                    branch="neighbor_overfit_trap" if trap else "behavior_timing_branch",
                    preferred_branch="behavior_timing_branch",
                    trap_branch=bool(trap),
                    branch_reason="waveform_branch_partially_reset" if trap else "waveform_behavior_gate_exposed",
                    transition_reason="stability_restored_behavior_gate_exposed",
                    bucket="single_case_only" if trap else "behavior_contract_miss",
                )
            else:
                return build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif "model hybrida" in lower_current:
            if re.search(r"\bk\s*=\s*1\.18\b", current_text or "") and re.search(r"height\s*=\s*1\.12\b", current_text or ""):
                return build_multistep_eval(
                    stage="stage_1",
                    transition_reason="stability_constraints_still_violated",
                    transition_seen=False,
                    pass_all=False,
                    bucket="stability_margin_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"startTime\s*=\s*0\.45\b", current_text or ""):
                trap = re.search(r"\bk\s*=\s*1\b", current_text or "") and re.search(r"height\s*=\s*1\b", current_text or "")
                return build_branching_stage_2_eval(
                    branch="neighbor_overfit_trap" if trap else "behavior_timing_branch",
                    preferred_branch="behavior_timing_branch",
                    trap_branch=bool(trap),
                    branch_reason="gain_and_height_reset_before_timing" if trap else "timing_gate_exposed_after_partial_stability_fix",
                    transition_reason="stability_restored_behavior_gate_exposed",
                    bucket="single_case_only" if trap else "behavior_contract_miss",
                )
            else:
                return build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif re.search(r"\bk\s*=\s*1\.18\b", current_text or "") and re.search(r"height\s*=\s*1\.12\b", current_text or ""):
            return build_multistep_eval(
                stage="stage_1",
                transition_reason="stability_constraints_still_violated",
                transition_seen=False,
                pass_all=False,
                bucket="stability_margin_miss",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": False},
                    {"scenario_id": "neighbor_a", "pass": False},
                    {"scenario_id": "neighbor_b", "pass": False},
                ],
            )
        elif re.search(r"startTime\s*=\s*0\.45\b", current_text or ""):
            trap = re.search(r"\bk\s*=\s*1\b", current_text or "") and re.search(r"height\s*=\s*1\b", current_text or "")
            return build_branching_stage_2_eval(
                branch="neighbor_overfit_trap" if trap else "behavior_timing_branch",
                preferred_branch="behavior_timing_branch",
                trap_branch=bool(trap),
                branch_reason="generic_stability_unlock_path",
                transition_reason="stability_restored_behavior_gate_exposed",
                bucket="single_case_only" if trap else "behavior_contract_miss",
            )
        else:
            return build_multistep_eval(
                stage="passed",
                transition_reason="all_multistep_contracts_cleared",
                transition_seen=True,
                pass_all=True,
                bucket="",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": True},
                    {"scenario_id": "neighbor_b", "pass": True},
                ],
            )
    elif declared == "behavior_then_robustness":
        lower_current = str(current_text or "").lower()
        if "model switchb" in lower_current:
            if re.search(r"startTime\s*=\s*(?:0\.75|0\.92)\b", current_text or "") and re.search(r"freqHz\s*=\s*(?:1\.6|1\.9)\b", current_text or ""):
                return build_multistep_eval(
                    stage="stage_1",
                    transition_reason="nominal_behavior_still_failing",
                    transition_seen=False,
                    pass_all=False,
                    bucket="behavior_contract_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"\bk\s*=\s*(?:0\.82|0\.88)\b", current_text or ""):
                trap = re.search(r"startTime\s*=\s*0\.3\b", current_text or "") or re.search(r"freqHz\s*=\s*1\b", current_text or "")
                return build_branching_stage_2_eval(
                    branch="nominal_overfit_trap" if trap else "neighbor_robustness_branch",
                    preferred_branch="neighbor_robustness_branch",
                    trap_branch=bool(trap),
                    branch_reason="nominal_gate_partially_or_fully_reset_before_neighbor_robustness" if trap else "neighbor_robustness_exposed_after_partial_nominal_fix",
                    transition_reason="nominal_behavior_restored_neighbor_robustness_exposed",
                    bucket="behavior_contract_miss" if trap else "single_case_only",
                )
            else:
                return build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif re.search(r"width\s*=\s*(?:62|68)\b", current_text or "") or re.search(r"period\s*=\s*(?:0\.85|1\.05)\b", current_text or ""):
            if re.search(r"width\s*=\s*(?:62|68)\b", current_text or "") and re.search(r"period\s*=\s*(?:0\.85|1\.05)\b", current_text or ""):
                return build_multistep_eval(
                    stage="stage_1",
                    transition_reason="nominal_behavior_still_failing",
                    transition_seen=False,
                    pass_all=False,
                    bucket="behavior_contract_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            return build_branching_stage_2_eval(
                branch="neighbor_robustness_branch",
                preferred_branch="neighbor_robustness_branch",
                trap_branch=False,
                branch_reason="shape_gate_partially_restored",
                transition_reason="nominal_behavior_restored_neighbor_robustness_exposed",
                bucket="single_case_only",
            )
        elif re.search(r"offset\s*=\s*(?:0\.2|0\.28)\b", current_text or ""):
            trap = re.search(r"width\s*=\s*40\b", current_text or "") and re.search(r"period\s*=\s*0\.5\b", current_text or "")
            return build_branching_stage_2_eval(
                branch="nominal_overfit_trap" if trap else "neighbor_robustness_branch",
                preferred_branch="neighbor_robustness_branch",
                trap_branch=bool(trap),
                branch_reason="shape_gate_fully_reset_before_offset_repair" if trap else "offset_robustness_exposed_after_partial_shape_fix",
                transition_reason="nominal_behavior_restored_neighbor_robustness_exposed",
                bucket="behavior_contract_miss" if trap else "single_case_only",
            )
        else:
            return build_multistep_eval(
                stage="passed",
                transition_reason="all_multistep_contracts_cleared",
                transition_seen=True,
                pass_all=True,
                bucket="",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": True},
                    {"scenario_id": "neighbor_b", "pass": True},
                ],
            )
    elif declared == "switch_then_recovery":
        lower_current = str(current_text or "").lower()
        if "model plantb" in lower_current:
            if re.search(r"startTime\s*=\s*(?:0\.6|0\.74)\b", current_text or "") and re.search(r"duration\s*=\s*(?:1\.1|1\.35)\b", current_text or ""):
                return build_multistep_eval(
                    stage="stage_1",
                    transition_reason="switch_window_still_unstable",
                    transition_seen=False,
                    pass_all=False,
                    bucket="scenario_switch_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"duration\s*=\s*(?:1\.1|1\.35)\b", current_text or ""):
                trap = re.search(r"startTime\s*=\s*0\.2\b", current_text or "")
                return build_branching_stage_2_eval(
                    branch="recovery_overfit_trap" if trap else "post_switch_recovery_branch",
                    preferred_branch="post_switch_recovery_branch",
                    trap_branch=bool(trap),
                    branch_reason="switch_timing_reset_before_recovery_duration" if trap else "recovery_segment_exposed_after_partial_switch_fix",
                    transition_reason="switch_segment_restored_recovery_gate_exposed",
                    bucket="single_case_only" if trap else "post_switch_recovery_miss",
                )
            else:
                return build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif "model switcha" in lower_current:
            if re.search(r"\bk\s*=\s*0\.6\b", current_text or ""):
                return build_multistep_eval(
                    stage="stage_1",
                    transition_reason="switch_window_still_unstable",
                    transition_seen=False,
                    pass_all=False,
                    bucket="scenario_switch_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"width\s*=\s*75\b", current_text or "") or re.search(r"period\s*=\s*1\.4\b", current_text or ""):
                trap = re.search(r"\bk\s*=\s*1\b", current_text or "")
                return build_branching_stage_2_eval(
                    branch="recovery_overfit_trap" if trap else "post_switch_recovery_branch",
                    preferred_branch="post_switch_recovery_branch",
                    trap_branch=bool(trap),
                    branch_reason="switch_gain_reset_before_recovery_window" if trap else "recovery_gate_exposed_after_partial_switch_fix",
                    transition_reason="switch_segment_restored_recovery_gate_exposed",
                    bucket="single_case_only" if trap else "post_switch_recovery_miss",
                )
            else:
                return build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif "model hybridb" in lower_current:
            if re.search(r"startTime\s*=\s*(?:0\.6|0\.72)\b", current_text or "") and re.search(r"\bk\s*=\s*(?:0\.6|0\.55)\b", current_text or ""):
                return build_multistep_eval(
                    stage="stage_1",
                    transition_reason="switch_window_still_unstable",
                    transition_seen=False,
                    pass_all=False,
                    bucket="scenario_switch_miss",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": False},
                        {"scenario_id": "neighbor_a", "pass": False},
                        {"scenario_id": "neighbor_b", "pass": False},
                    ],
                )
            elif re.search(r"width\s*=\s*(?:0\.75|0\.9)\b", current_text or "") or re.search(r"\bT\s*=\s*(?:0\.5|0\.62)\b", current_text or ""):
                trap = re.search(r"startTime\s*=\s*0\.1\b", current_text or "") or re.search(r"\bk\s*=\s*1\b", current_text or "")
                return build_branching_stage_2_eval(
                    branch="recovery_overfit_trap" if trap else "post_switch_recovery_branch",
                    preferred_branch="post_switch_recovery_branch",
                    trap_branch=bool(trap),
                    branch_reason="switch_gate_partially_or_fully_reset_before_recovery_shape" if trap else "recovery_shape_exposed_after_partial_switch_fix",
                    transition_reason="switch_segment_restored_recovery_gate_exposed",
                    bucket="single_case_only" if trap else "post_switch_recovery_miss",
                )
            else:
                return build_multistep_eval(
                    stage="passed",
                    transition_reason="all_multistep_contracts_cleared",
                    transition_seen=True,
                    pass_all=True,
                    bucket="",
                    scenario_results=[
                        {"scenario_id": "nominal", "pass": True},
                        {"scenario_id": "neighbor_a", "pass": True},
                        {"scenario_id": "neighbor_b", "pass": True},
                    ],
                )
        elif re.search(r"startTime\s*=\s*0\.6\b", current_text or "") and re.search(r"\bk\s*=\s*0\.6\b", current_text or ""):
            return build_multistep_eval(
                stage="stage_1",
                transition_reason="switch_window_still_unstable",
                transition_seen=False,
                pass_all=False,
                bucket="scenario_switch_miss",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": False},
                    {"scenario_id": "neighbor_a", "pass": False},
                    {"scenario_id": "neighbor_b", "pass": False},
                ],
            )
        elif re.search(r"width\s*=\s*75\b", current_text or "") or re.search(r"period\s*=\s*1\.4\b", current_text or ""):
            trap = re.search(r"\bk\s*=\s*1\b", current_text or "") or re.search(r"startTime\s*=\s*0\.1\b", current_text or "")
            return build_branching_stage_2_eval(
                branch="recovery_overfit_trap" if trap else "post_switch_recovery_branch",
                preferred_branch="post_switch_recovery_branch",
                trap_branch=bool(trap),
                branch_reason="generic_switch_unlock_path",
                transition_reason="switch_segment_restored_recovery_gate_exposed",
                bucket="single_case_only" if trap else "post_switch_recovery_miss",
            )
        else:
            return build_multistep_eval(
                stage="passed",
                transition_reason="all_multistep_contracts_cleared",
                transition_seen=True,
                pass_all=True,
                bucket="",
                scenario_results=[
                    {"scenario_id": "nominal", "pass": True},
                    {"scenario_id": "neighbor_a", "pass": True},
                    {"scenario_id": "neighbor_b", "pass": True},
                ],
            )
    return {
        "pass": passed,
        "reasons": [] if passed else (["single_case_only", bucket] if scenario_results else [bucket]),
        "contract_fail_bucket": "" if passed else bucket,
        "scenario_results": scenario_results or [],
    }


def apply_initialization_marker_repair(
    *,
    current_text: str,
    declared_failure_type: str,
) -> tuple[str, dict]:
    declared = str(declared_failure_type or "").strip().lower()
    if declared != "initialization_infeasible":
        return current_text, {"applied": False, "reason": "declared_failure_type_not_supported"}
    lines = str(current_text or "").splitlines(keepends=True)
    if not lines:
        return current_text, {"applied": False, "reason": "model_text_empty"}
    remove_idx: set[int] = set()
    for idx, line in enumerate(lines):
        if "gateforge_initialization_infeasible" not in line.lower():
            continue
        remove_idx.add(idx)
        prev = idx - 1
        while prev >= 0 and not lines[prev].strip():
            remove_idx.add(prev)
            prev -= 1
        if prev >= 0 and lines[prev].strip().lower() == "initial equation":
            remove_idx.add(prev)
    if not remove_idx:
        return current_text, {"applied": False, "reason": "initialization_marker_not_detected"}
    kept = [line for idx, line in enumerate(lines) if idx not in remove_idx]
    return "".join(kept), {
        "applied": True,
        "reason": "removed_gateforge_initialization_marker_block",
        "removed_line_count": int(len(remove_idx)),
    }

