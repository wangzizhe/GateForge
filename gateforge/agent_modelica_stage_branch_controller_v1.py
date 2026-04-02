"""Layer 3 Stage/Branch State Machine for multistep repair.

Extracted from agent_modelica_live_executor_v1.py to enable
independent testing and reuse. All functions are pure: they consume
plain dicts and return plain dicts, with no I/O, Docker, LLM, or OMC
dependencies.

State structure: ``make_multistep_memory()`` returns the canonical
155-key dict. Keys are grouped by concern:

**Stage progression** (8 keys):
    stage_1_unlock_cluster, stage_2_first_fail_bucket, stage_2_branch,
    preferred_stage_2_branch, branch_reason, stage_2_transition_round,
    stage_2_transition_reason, best_stage_2_fail_bucket_seen

**Trap/branch tracking** (12 keys):
    trap_branch_active, trap_branch_entered, correct_branch_selected,
    correct_branch_round, branch_history, trap_branch_history,
    branch_reentry_count, branch_escape_attempt_count,
    branch_escape_success_count, last_trap_escape_direction,
    last_successful_branch_correction, branch_bad_directions

**Plan tracking** (14 keys):
    last_plan_stage, last_plan_goal, last_plan_actions, ...

**Search tracking** (10 keys):
    tried_parameters, bad_directions, successful_directions, ...

**LLM plan** (30+ keys):
    llm_plan_used, llm_plan_reason, llm_plan_generated, ...

**Budget** (15+ keys):
    budget_bucket_consumed, budget_bucket_exhausted, ...

**Guided search** (15+ keys):
    guided_search_bucket_sequence, guided_search_order, ...
"""
from __future__ import annotations

import argparse
import json
import re


SCHEMA_VERSION = "agent_modelica_stage_branch_controller_v1"


# ---------------------------------------------------------------------------
# Bucket mapping
# ---------------------------------------------------------------------------

def behavioral_contract_bucket(failure_type: str) -> str:
    """Map a failure_type string to a behavioral contract bucket."""
    mapping = {
        "steady_state_target_violation": "steady_state_miss",
        "transient_response_contract_violation": "overshoot_or_settling_violation",
        "mode_transition_contract_violation": "mode_transition_miss",
        "param_perturbation_robustness_violation": "param_sensitivity_miss",
        "initial_condition_robustness_violation": "initial_condition_miss",
        "scenario_switch_robustness_violation": "scenario_switch_miss",
        "stability_then_behavior": "stability_margin_miss",
        "behavior_then_robustness": "single_case_only",
        "switch_then_recovery": "scenario_switch_miss",
    }
    return mapping.get(str(failure_type or "").strip().lower(), "behavioral_contract_fail")


# ---------------------------------------------------------------------------
# Core eval builder
# ---------------------------------------------------------------------------

def build_multistep_eval(
    *,
    stage: str,
    transition_reason: str,
    transition_seen: bool,
    pass_all: bool,
    bucket: str,
    scenario_results: list[dict],
    stage_2_branch: str = "",
    preferred_stage_2_branch: str = "",
    branch_reason: str = "",
    trap_branch: bool = False,
    correct_branch_selected: bool = False,
) -> dict:
    """Build a multistep behavioral evaluation payload dict."""
    stage_norm = str(stage or "").strip().lower()
    unlocked = stage_norm in {"stage_2", "passed"}
    passed = bool(pass_all)
    return {
        "pass": passed,
        "reasons": [] if passed else (["single_case_only", bucket] if scenario_results else [bucket]),
        "contract_fail_bucket": "" if passed else bucket,
        "scenario_results": scenario_results or [],
        "multi_step_stage": stage_norm,
        "multi_step_stage_2_unlocked": bool(unlocked),
        "multi_step_transition_seen": bool(transition_seen),
        "multi_step_transition_reason": str(transition_reason or ""),
        "stage_2_branch": str(stage_2_branch or ""),
        "preferred_stage_2_branch": str(preferred_stage_2_branch or ""),
        "branch_reason": str(branch_reason or ""),
        "trap_branch": bool(trap_branch),
        "correct_branch_selected": bool(correct_branch_selected),
    }


# ---------------------------------------------------------------------------
# Focus / branch-mode computation
# ---------------------------------------------------------------------------

def multistep_stage_default_focus(*, failure_type: str, stage: str, fail_bucket: str, stage_2_branch: str = "", trap_branch: bool = False) -> str:
    """Compute the next repair focus directive based on stage/branch state."""
    ftype = str(failure_type or "").strip().lower()
    stage_norm = str(stage or "").strip().lower()
    bucket = str(fail_bucket or "").strip().lower()
    if stage_norm in {"", "stage_1"}:
        mapping = {
            "stability_then_behavior": "unlock_stage_2_behavior_gate",
            "behavior_then_robustness": "unlock_stage_2_neighbor_robustness_gate",
            "switch_then_recovery": "unlock_stage_2_recovery_gate",
        }
        return mapping.get(ftype, "unlock_stage_2")
    if stage_norm == "stage_2":
        branch = str(stage_2_branch or "").strip().lower()
        if branch:
            branch_mapping = {
                "behavior_timing_branch": "resolve_stage_2_behavior_timing",
                "neighbor_robustness_branch": "resolve_stage_2_neighbor_robustness",
                "post_switch_recovery_branch": "resolve_stage_2_post_switch_recovery",
                "neighbor_overfit_trap": "escape_trap_branch_neighbor_overfit",
                "nominal_overfit_trap": "escape_trap_branch_nominal_overfit",
                "recovery_overfit_trap": "escape_trap_branch_recovery_overfit",
            }
            if trap_branch:
                return branch_mapping.get(branch, "escape_trap_branch")
            return branch_mapping.get(branch, "resolve_stage_2_branch_specific_failure")
        mapping = {
            "behavior_contract_miss": "resolve_stage_2_behavior_contract",
            "single_case_only": "resolve_stage_2_neighbor_robustness",
            "post_switch_recovery_miss": "resolve_stage_2_post_switch_recovery",
        }
        return mapping.get(bucket, "resolve_stage_2_exposed_failure")
    if stage_norm == "passed":
        return "stop_editing"
    return "inspect_current_stage"


def multistep_branch_mode(*, current_stage: str, stage_2_branch: str, preferred_stage_2_branch: str, trap_branch: bool) -> str:
    """Determine branch mode: empty, trap, preferred, or unknown."""
    stage = str(current_stage or "").strip().lower()
    branch = str(stage_2_branch or "").strip().lower()
    preferred = str(preferred_stage_2_branch or "").strip().lower()
    if stage != "stage_2":
        return ""
    if trap_branch:
        return "trap"
    if branch and preferred and branch == preferred:
        return "preferred"
    if branch:
        return "unknown"
    return ""


def looks_like_stage_1_focus(*, failure_type: str, action: str) -> bool:
    """Heuristic: does the given action text look like a stage-1 repair?"""
    ftype = str(failure_type or "").strip().lower()
    lower = str(action or "").strip().lower()
    if any(
        token in lower
        for token in (
            "stop revisiting",
            "do not reopen",
            "reject edits that reopen",
            "reintroduce stage-1",
            "after stage_2 unlock",
            "rank second-layer repair above",
        )
    ):
        return False
    signatures = {
        "stability_then_behavior": ("stability", "startup timing", "unlock step"),
        "behavior_then_robustness": ("nominal behavior", "unlock step", "primary scenario"),
        "switch_then_recovery": ("switch timing", "trigger", "unlock step"),
    }
    return any(token in lower for token in signatures.get(ftype, ()))


# ---------------------------------------------------------------------------
# Stage context synthesis (the heart of Layer 3)
# ---------------------------------------------------------------------------

def build_multistep_stage_context(
    *,
    failure_type: str,
    behavioral_eval: dict | None,
    current_round: int,
    memory: dict,
) -> dict:
    """Synthesize stage context from behavioral evaluation + memory.

    This is the core Layer 3 function. It reads the latest eval output
    and accumulated memory to produce a context dict consumed by
    Layer 4 (search engine) and Layer 2 (plan/replan).
    """
    eval_payload = behavioral_eval if isinstance(behavioral_eval, dict) else {}
    current_stage = str(eval_payload.get("multi_step_stage") or "").strip().lower()
    current_fail_bucket = str(eval_payload.get("contract_fail_bucket") or "").strip().lower()
    stage_2_unlocked = bool(eval_payload.get("multi_step_stage_2_unlocked"))
    transition_round = int(memory.get("stage_2_transition_round") or 0)
    if stage_2_unlocked and transition_round <= 0:
        transition_round = int(current_round)
    transition_reason = str(
        memory.get("stage_2_transition_reason")
        or eval_payload.get("multi_step_transition_reason")
        or ""
    ).strip()
    stage_2_first_fail_bucket = str(memory.get("stage_2_first_fail_bucket") or "").strip().lower()
    if stage_2_unlocked and current_fail_bucket and not stage_2_first_fail_bucket:
        stage_2_first_fail_bucket = current_fail_bucket
    stage_2_branch = str(
        eval_payload.get("stage_2_branch")
        or memory.get("stage_2_branch")
        or ""
    ).strip().lower()
    preferred_stage_2_branch = str(
        eval_payload.get("preferred_stage_2_branch")
        or memory.get("preferred_stage_2_branch")
        or ""
    ).strip().lower()
    branch_reason = str(
        eval_payload.get("branch_reason")
        or memory.get("branch_reason")
        or ""
    ).strip()
    if stage_2_branch:
        trap_branch = bool(eval_payload.get("trap_branch"))
        correct_branch_selected = bool(eval_payload.get("correct_branch_selected"))
    else:
        trap_branch = bool(memory.get("trap_branch_active"))
        correct_branch_selected = bool(memory.get("correct_branch_selected"))
    next_focus = multistep_stage_default_focus(
        failure_type=failure_type,
        stage=current_stage,
        fail_bucket=current_fail_bucket or stage_2_first_fail_bucket,
        stage_2_branch=stage_2_branch,
        trap_branch=trap_branch,
    )
    branch_mode = multistep_branch_mode(
        current_stage=current_stage,
        stage_2_branch=stage_2_branch,
        preferred_stage_2_branch=preferred_stage_2_branch,
        trap_branch=trap_branch,
    )
    return {
        "current_stage": current_stage,
        "stage_2_unlocked": stage_2_unlocked,
        "transition_round": transition_round,
        "transition_reason": transition_reason,
        "current_fail_bucket": current_fail_bucket,
        "next_focus": next_focus,
        "stage_1_unlock_cluster": str(memory.get("stage_1_unlock_cluster") or ""),
        "stage_2_first_fail_bucket": stage_2_first_fail_bucket,
        "stage_2_branch": stage_2_branch,
        "preferred_stage_2_branch": preferred_stage_2_branch,
        "branch_mode": branch_mode,
        "branch_reason": branch_reason,
        "trap_branch": trap_branch,
        "correct_branch_selected": correct_branch_selected,
    }


# ---------------------------------------------------------------------------
# Plan field extraction
# ---------------------------------------------------------------------------

def stage_plan_fields(*, plan: dict | None, generated: bool, followed: bool, conflict_rejected: bool, conflict_rejected_count: int, executed_action: str) -> dict:
    """Extract plan tracking fields from a plan dict."""
    payload = plan if isinstance(plan, dict) else {}
    return {
        "plan_stage": str(payload.get("plan_stage") or ""),
        "branch_stage": str(payload.get("branch_stage") or ""),
        "current_branch": str(payload.get("current_branch") or ""),
        "preferred_branch": str(payload.get("preferred_branch") or ""),
        "branch_mode": str(payload.get("branch_mode") or ""),
        "plan_goal": str(payload.get("plan_goal") or ""),
        "plan_actions": [str(x) for x in (payload.get("plan_actions") or []) if isinstance(x, str)],
        "plan_constraints": [str(x) for x in (payload.get("plan_constraints") or []) if isinstance(x, str)],
        "plan_stop_condition": str(payload.get("plan_stop_condition") or ""),
        "branch_plan_goal": str(payload.get("branch_plan_goal") or ""),
        "branch_plan_actions": [str(x) for x in (payload.get("branch_plan_actions") or []) if isinstance(x, str)],
        "branch_plan_stop_condition": str(payload.get("branch_plan_stop_condition") or ""),
        "stage_plan_generated": bool(generated),
        "stage_plan_followed": bool(followed),
        "executed_plan_stage": str(payload.get("plan_stage") or ""),
        "executed_plan_action": str(executed_action or ""),
        "plan_followed": bool(followed),
        "plan_conflict_rejected": bool(conflict_rejected),
        "plan_conflict_rejected_count": max(0, int(conflict_rejected_count or 0)),
    }


# ---------------------------------------------------------------------------
# Source-blind multistep markers
# ---------------------------------------------------------------------------

def extract_source_blind_multistep_markers(model_text: str) -> dict:
    """Extract GateForge markers embedded in Modelica model text."""
    text = str(model_text or "")
    markers: dict = {
        "realism_version": "",
        "llm_forcing": False,
        "llm_profile": "",
        "llm_trigger": "",
    }
    patterns = {
        "realism_version": r"gateforge_source_blind_multistep_realism_version:([A-Za-z0-9_\-]+)",
        "llm_profile": r"gateforge_source_blind_multistep_llm_profile:([A-Za-z0-9_\-]+)",
        "llm_trigger": r"gateforge_source_blind_multistep_llm_trigger:([A-Za-z0-9_\-]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            markers[key] = str(match.group(1) or "").strip().lower()
    markers["llm_forcing"] = bool(
        re.search(r"gateforge_source_blind_multistep_llm_forcing:(?:1|true|yes)\b", text, flags=re.IGNORECASE)
    )
    return markers


# ---------------------------------------------------------------------------
# LLM context builders
# ---------------------------------------------------------------------------

def build_source_blind_multistep_llm_context(
    *,
    current_text: str,
    stage_context: dict,
    current_round: int,
    memory: dict,
) -> dict:
    """Compute LLM forcing context: whether and why the LLM should be called."""
    markers = extract_source_blind_multistep_markers(current_text)
    current_stage = str(stage_context.get("current_stage") or "").strip().lower()
    current_branch = str(stage_context.get("stage_2_branch") or "").strip().lower()
    current_bucket = str(stage_context.get("current_fail_bucket") or "").strip().lower()
    branch_mode = str(stage_context.get("branch_mode") or "").strip().lower()
    trap_branch = bool(stage_context.get("trap_branch"))
    signatures = list(memory.get("llm_force_signatures") or [])
    signature = f"{current_stage}:{current_branch or current_bucket or 'unknown'}"
    consecutive_same_branch = bool(len(signatures) >= 1 and signatures[-1] == signature)
    candidate_pool_exhausted = (
        current_stage in {"stage_1", "stage_2"}
        and current_round >= 2
        and not bool(memory.get("search_improvement_seen"))
    )
    reason = ""
    if not bool(markers.get("llm_forcing")):
        reason = ""
    elif branch_mode == "unknown":
        reason = "branch_diagnosis_unknown"
    elif trap_branch and int(memory.get("branch_escape_attempt_count") or 0) > int(memory.get("branch_escape_success_count") or 0):
        reason = "trap_escape_no_progress"
    elif current_stage == "stage_2" and current_branch and consecutive_same_branch:
        reason = "same_stage_2_branch_stall"
    elif candidate_pool_exhausted:
        reason = "candidate_pool_exhausted"
    elif str(markers.get("llm_trigger") or "").strip():
        reason = str(markers.get("llm_trigger") or "").strip().lower()
    return {
        **markers,
        "current_stage": current_stage,
        "current_branch": current_branch,
        "current_fail_bucket": current_bucket,
        "branch_mode": branch_mode,
        "trap_branch": trap_branch,
        "signature": signature,
        "same_stage_2_branch_stall": consecutive_same_branch,
        "candidate_pool_exhausted": candidate_pool_exhausted,
        "should_force_llm": bool(markers.get("llm_forcing")) and bool(reason),
        "llm_plan_reason": reason,
    }


def count_passed_scenarios(rows: list[dict] | None) -> int:
    """Count the number of passing scenarios in a scenario_results list."""
    return sum(1 for row in (rows or []) if isinstance(row, dict) and bool(row.get("pass")))


def build_source_blind_multistep_llm_replan_context(
    *,
    current_text: str,
    stage_context: dict,
    current_round: int,
    memory: dict,
    contract_fail_bucket: str,
    scenario_results: list[dict] | None,
) -> dict:
    """Compute replan decision context: whether to trigger a replan and why."""
    markers = extract_source_blind_multistep_markers(current_text)
    realism_version = str(markers.get("realism_version") or "").strip().lower()
    replan_forcing = bool(markers.get("llm_forcing")) and realism_version in {"v4", "v5"}
    previous_plan_followed = bool(memory.get("llm_plan_followed"))
    replan_count = int(memory.get("llm_replan_count") or 0)
    max_replans = 2 if realism_version == "v5" else 1
    already_replanned = replan_count >= max_replans
    current_stage = str(stage_context.get("current_stage") or "").strip().lower()
    current_branch = str(stage_context.get("stage_2_branch") or "").strip().lower()
    preferred_branch = str(stage_context.get("preferred_stage_2_branch") or "").strip().lower()
    branch_mode = str(stage_context.get("branch_mode") or "").strip().lower()
    trap_branch = bool(stage_context.get("trap_branch"))
    prev_branch = str(memory.get("last_llm_plan_branch") or memory.get("new_branch") or "").strip().lower()
    prev_fail_bucket = str(memory.get("last_llm_plan_fail_bucket") or "").strip().lower()
    prev_pass_count = int(memory.get("last_llm_plan_pass_count") or 0)
    previous_request_kind = str(memory.get("last_llm_request_kind") or "").strip().lower()
    current_fail_bucket = str(contract_fail_bucket or stage_context.get("current_fail_bucket") or "").strip().lower()
    current_pass_count = count_passed_scenarios(scenario_results)
    signal = ""
    if not replan_forcing or not previous_plan_followed or already_replanned or current_round < 2:
        signal = ""
    elif current_stage == "stage_1":
        signal = "regressed_to_stage_1_after_first_plan"
    elif trap_branch and previous_request_kind == "replan":
        signal = "trap_branch_persisted_after_replan"
    elif trap_branch and int(memory.get("branch_escape_attempt_count") or 0) <= int(memory.get("branch_escape_success_count") or 0):
        signal = "trap_branch_no_escape_progress"
    elif current_branch and prev_branch and current_branch == prev_branch:
        signal = "same_stage_2_branch_stall_after_replan" if replan_count > 0 else "same_stage_2_branch_stall_after_first_plan"
    elif branch_mode == "unknown":
        signal = "branch_mode_unknown_after_replan" if replan_count > 0 else "branch_mode_unknown_after_first_plan"
    elif current_fail_bucket and prev_fail_bucket and current_fail_bucket == prev_fail_bucket and current_pass_count <= prev_pass_count:
        signal = "no_contract_bucket_progress_after_replan" if replan_count > 0 else "no_contract_bucket_progress_after_first_plan"
    elif current_branch and preferred_branch and current_branch != preferred_branch:
        signal = "replan_did_not_reach_preferred_branch" if replan_count > 0 else "partial_progress_without_preferred_branch"
    elif int(memory.get("adaptive_search_attempt_count") or 0) > 0 and not bool(memory.get("search_improvement_seen")):
        signal = "candidate_pool_exhausted_after_replan" if replan_count > 0 else "candidate_pool_exhausted_after_first_plan"
    return {
        "llm_replan_forcing": replan_forcing,
        "should_force_replan": bool(signal),
        "previous_plan_failed_signal": signal,
        "llm_replan_reason": signal,
        "previous_branch": prev_branch or current_branch,
        "current_branch": current_branch,
        "preferred_branch": preferred_branch,
        "current_fail_bucket": current_fail_bucket,
        "current_pass_count": current_pass_count,
        "realism_version": realism_version,
        "replan_count_before": replan_count,
        "max_replans": max_replans,
        "previous_request_kind": previous_request_kind,
    }


def build_source_blind_multistep_replan_budget(
    *,
    stage_context: dict,
    replan_context: dict,
    current_round: int,
    max_rounds: int,
    memory: dict,
) -> dict:
    """Compute replan budget allocation across branch_diagnosis / branch_escape / resolution."""
    signal = str(replan_context.get("previous_plan_failed_signal") or "").strip().lower()
    realism_version = str(replan_context.get("realism_version") or "").strip().lower()
    replan_count_before = int(replan_context.get("replan_count_before") or 0)
    current_branch = str(replan_context.get("current_branch") or stage_context.get("stage_2_branch") or "").strip().lower()
    preferred_branch = str(replan_context.get("preferred_branch") or stage_context.get("preferred_stage_2_branch") or "").strip().lower()
    trap_branch = bool(stage_context.get("trap_branch"))
    remaining_rounds = max(1, int(max_rounds) - int(current_round) + 1)
    switch_signals = {
        "trap_branch_no_escape_progress",
        "partial_progress_without_preferred_branch",
        "same_stage_2_branch_stall_after_first_plan",
        "regressed_to_stage_1_after_first_plan",
    }
    if current_branch and preferred_branch and current_branch == preferred_branch and signal == "same_stage_2_branch_stall_after_first_plan":
        switch_signals = {name for name in switch_signals if name != "same_stage_2_branch_stall_after_first_plan"}
    should_switch = bool(preferred_branch) and (
        trap_branch
        or signal in switch_signals
        or (current_branch and preferred_branch and current_branch != preferred_branch)
    )
    continue_current_branch = not should_switch
    diagnosis_budget = 1
    branch_escape_budget = 1 if should_switch or trap_branch else 0
    resolution_budget = max(1, remaining_rounds - diagnosis_budget - branch_escape_budget)
    if current_branch and preferred_branch and current_branch == preferred_branch and signal == "same_stage_2_branch_stall_after_first_plan":
        diagnosis_budget = 0
        branch_escape_budget = 0
        resolution_budget = max(2, remaining_rounds)
    if realism_version == "v5" and replan_count_before >= 1:
        if current_branch and preferred_branch and current_branch == preferred_branch:
            should_switch = False
            continue_current_branch = True
            diagnosis_budget = 0
            branch_escape_budget = 0
            resolution_budget = max(2, remaining_rounds + 1)
        elif trap_branch or (current_branch and preferred_branch and current_branch != preferred_branch):
            should_switch = True
            continue_current_branch = False
            diagnosis_budget = 0
            branch_escape_budget = max(1, remaining_rounds)
            resolution_budget = max(2, remaining_rounds + 1)
    total_budget = diagnosis_budget + branch_escape_budget + resolution_budget
    if should_switch and current_branch:
        branch_choice_reason = f"switch away from '{current_branch}' because '{signal or 'trap branch detected'}' suggests the preferred branch is better"
    elif continue_current_branch and current_branch:
        branch_choice_reason = f"continue on '{current_branch}' because the signal '{signal or 'no_progress'}' suggests deeper branch-local search before switching"
    else:
        branch_choice_reason = f"spend the first budget slice on branch diagnosis because the current signal is '{signal or 'unknown'}'"
    budget_history = [row for row in (memory.get("replan_budget_history") or []) if isinstance(row, dict)]
    budget_history.append(
        {
            "round": int(current_round),
            "signal": signal,
            "total": total_budget,
            "branch_diagnosis": diagnosis_budget,
            "branch_escape": branch_escape_budget,
            "resolution": resolution_budget,
            "continue_current_branch": continue_current_branch,
            "switch_branch": should_switch,
            "current_branch": current_branch,
            "preferred_branch": preferred_branch,
        }
    )
    return {
        "replan_budget_total": total_budget,
        "replan_budget_for_branch_diagnosis": diagnosis_budget,
        "replan_budget_for_branch_escape": branch_escape_budget,
        "replan_budget_for_resolution": resolution_budget,
        "replan_budget_consumed": 0,
        "replan_continue_current_branch": continue_current_branch,
        "replan_switch_branch": should_switch,
        "branch_choice_reason": branch_choice_reason,
        "replan_budget_history": budget_history,
    }


# ---------------------------------------------------------------------------
# Branching eval convenience
# ---------------------------------------------------------------------------

def build_branching_stage_2_eval(
    *,
    branch: str,
    preferred_branch: str,
    trap_branch: bool,
    branch_reason: str,
    transition_reason: str,
    bucket: str,
) -> dict:
    """Build a stage-2 branching behavioral evaluation dict."""
    return build_multistep_eval(
        stage="stage_2",
        transition_reason=transition_reason,
        transition_seen=True,
        pass_all=False,
        bucket=bucket,
        scenario_results=[
            {"scenario_id": "nominal", "pass": True},
            {"scenario_id": "neighbor_a", "pass": False},
            {"scenario_id": "neighbor_b", "pass": False},
        ],
        stage_2_branch=branch,
        preferred_stage_2_branch=preferred_branch,
        branch_reason=branch_reason,
        trap_branch=trap_branch,
        correct_branch_selected=not trap_branch,
    )


# ---------------------------------------------------------------------------
# multistep_memory factory
# ---------------------------------------------------------------------------

def make_multistep_memory() -> dict:
    """Return a fresh multistep_memory dict with all 155 keys at defaults.

    This is the single source of truth for the state structure consumed
    and mutated by the repair loop.
    """
    return {
        # --- Stage progression ---
        "stage_1_unlock_cluster": "",
        "stage_2_first_fail_bucket": "",
        "stage_2_branch": "",
        "preferred_stage_2_branch": "",
        "branch_history": [],
        "trap_branch_history": [],
        "branch_reason": "",
        "trap_branch_active": False,
        "trap_branch_entered": False,
        "correct_branch_selected": False,
        "correct_branch_round": 0,
        "last_trap_escape_direction": "",
        "last_successful_branch_correction": "",
        "branch_bad_directions": [],
        "branch_reentry_count": 0,
        "branch_escape_attempt_count": 0,
        "branch_escape_success_count": 0,
        "branch_budget_reallocated_count": 0,
        "stage_2_transition_round": 0,
        "stage_2_transition_reason": "",
        "stage_aware_focus_applied": False,
        "stage_1_revisit_after_unlock": False,
        # --- Plan tracking ---
        "last_plan_stage": "",
        "last_plan_goal": "",
        "last_plan_actions": [],
        "last_plan_constraints": [],
        "last_plan_stop_condition": "",
        "stage_plan_generated": False,
        "stage_plan_followed": False,
        "executed_plan_stage": "",
        "executed_plan_action": "",
        "plan_conflict_rejected": False,
        "plan_conflict_rejected_count": 0,
        "last_successful_stage_action": "",
        # --- Search tracking ---
        "tried_parameters": [],
        "tried_candidate_values": [],
        "bad_directions": [],
        "successful_directions": [],
        "local_search_attempt_count": 0,
        "local_search_success_count": 0,
        "local_search_kinds": [],
        "adaptive_search_attempt_count": 0,
        "adaptive_search_success_count": 0,
        "search_improvement_seen": False,
        "search_regression_seen": False,
        "search_bad_direction_count": 0,
        "best_stage_2_fail_bucket_seen": "",
        "stage_2_best_progress_seen": False,
        "stage_1_unlock_via_local_search": False,
        "stage_2_resolution_via_local_search": False,
        "cluster_only_resolution": False,
        # --- LLM plan ---
        "llm_force_signatures": [],
        "llm_plan_used": False,
        "llm_plan_reason": "",
        "llm_request_count_delta_total": 0,
        "llm_branch_correction_used": False,
        "llm_resolution_contributed": False,
        "llm_only_resolution": False,
        "llm_plan_generated": False,
        "llm_plan_parsed": False,
        "llm_plan_followed": False,
        "planner_contract_version": "",
        "planner_family": "",
        "planner_adapter": "",
        "planner_request_kind": "",
        "llm_plan_branch_match": False,
        "first_plan_branch_match": False,
        "first_plan_branch_miss": False,
        "replan_branch_match": False,
        "replan_branch_corrected": False,
        "llm_plan_parameter_match": False,
        "llm_plan_helped_resolution": False,
        "llm_plan_was_decisive": False,
        "llm_called_only": False,
        "llm_plan_failure_mode": "",
        "llm_plan_diagnosed_stage": "",
        "llm_plan_diagnosed_branch": "",
        "llm_plan_preferred_branch": "",
        "llm_plan_repair_goal": "",
        "llm_plan_candidate_parameters": [],
        "llm_plan_candidate_value_directions": [],
        "llm_plan_why_not_other_branch": "",
        "llm_plan_stop_condition": "",
        "last_llm_plan_round": 0,
        "last_llm_plan_branch": "",
        "last_llm_plan_fail_bucket": "",
        "last_llm_plan_pass_count": 0,
        "last_llm_plan_candidate_parameters": [],
        "last_llm_plan_candidate_value_directions": [],
        # --- Replan ---
        "llm_replan_used": False,
        "llm_replan_reason": "",
        "llm_replan_count": 0,
        "llm_second_replan_used": False,
        "llm_second_replan_reason": "",
        "previous_plan_failed_signal": "",
        "previous_branch": "",
        "new_branch": "",
        "replan_goal": "",
        "replan_candidate_parameters": [],
        "replan_stop_condition": "",
        "branch_choice_reason": "",
        "replan_budget_total": 0,
        "replan_budget_for_branch_diagnosis": 0,
        "replan_budget_for_branch_escape": 0,
        "replan_budget_for_resolution": 0,
        "replan_budget_consumed": 0,
        "replan_continue_current_branch": False,
        "replan_switch_branch": False,
        "replan_history": [],
        "replan_branch_history": [],
        "replan_failed_directions": [],
        "replan_successful_directions": [],
        "replan_same_branch_stall_count": 0,
        "replan_switch_branch_count": 0,
        "replan_abandoned_branches": [],
        "replan_budget_history": [],
        "backtracking_used": False,
        "backtracking_reason": "",
        "budget_reallocated_after_replan": False,
        "abandoned_plan_directions": [],
        "replan_branch_correction_used": False,
        "replan_helped_resolution": False,
        "llm_first_plan_resolved": False,
        "llm_replan_resolved": False,
        # --- Guided search ---
        "llm_guided_search_used": False,
        "search_budget_from_llm_plan": 0,
        "search_budget_followed": False,
        "llm_budget_helped_resolution": False,
        "llm_guided_search_resolution": False,
        "guided_search_bucket_sequence": [],
        "guided_search_order": "",
        "budget_bucket_consumed": {},
        "budget_bucket_exhausted": [],
        "candidate_suppressed_by_budget": 0,
        "branch_frozen_by_budget": [],
        "resolution_skipped_due_to_budget": False,
        "branch_escape_skipped_due_to_budget": False,
        "guided_search_observation_payload": {},
        "guided_search_replan_after_observation": False,
        "guided_search_closed_loop_observed": False,
        "guided_search_helped_branch_diagnosis": False,
        "guided_search_helped_trap_escape": False,
        "guided_search_helped_resolution": False,
        "guided_search_helped_replan": False,
        "guided_search_was_decisive": False,
        "resolution_primary_contribution": "",
        "last_guided_search_bucket_sequence": [],
        "last_budget_spent_by_bucket": {},
        "last_candidate_attempt_count_by_bucket": {},
        "last_candidate_suppressed_by_budget": 0,
        "last_resolution_skipped_due_to_budget": False,
        "last_branch_escape_skipped_due_to_budget": False,
        "last_branch_frozen_by_budget": [],
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Layer 3 Stage/Branch State Machine — inspect schema"
    )
    parser.add_argument(
        "--show-memory-keys",
        action="store_true",
        help="Print all multistep_memory keys and exit",
    )
    args = parser.parse_args()

    if args.show_memory_keys:
        memory = make_multistep_memory()
        print(json.dumps({"schema_version": SCHEMA_VERSION, "key_count": len(memory), "keys": sorted(memory.keys())}, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
