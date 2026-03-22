from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RULES = {
    "underconstrained_system": [
        "restore the missing connect(...) edge before declaration or equation rewrites",
        "restore dangling conservation path and connector balance before any simulate retry",
        "rerun checkModel immediately after each topology repair step",
    ],
    "model_check_error": [
        "scan undefined symbols and missing declarations",
        "resolve connector/causality mismatches before simulation",
        "rerun checkModel after each localized patch",
    ],
    "simulate_error": [
        "stabilize initialization and start values",
        "bound unstable parameters and solver-sensitive constants",
        "rerun simulate after compile passes",
    ],
    "semantic_regression": [
        "restore sign/unit consistency for dominant components",
        "re-check behavioral metrics against baseline before merge",
        "enforce no-regression guard before final accept",
    ],
    "solver_sensitive_simulate_failure": [
        "restore source solver-facing parameters before broad edits",
        "reduce stiff or chattering dynamics before another simulate retry",
        "rerun simulate with conservative settings after localized repair",
    ],
    "event_logic_error": [
        "restore source event thresholds and reinit conditions first",
        "limit event logic repair to the injected when/assert block before wider edits",
        "rerun simulate and inspect event timing before accepting the patch",
    ],
    "semantic_drift_after_compile_pass": [
        "restore sign-sensitive dynamic equations to source-local behavior",
        "avoid broad topology edits when the drift is localized to injected dynamics",
        "rerun simulate and compare semantic behavior before accepting the patch",
    ],
    "cross_component_parameter_coupling_error": [
        "restore source cross-component parameter relationships before broad edits",
        "limit repair to injected coupled states and wrong gain bindings first",
        "rerun simulate and inspect the coupled response before accepting the patch",
    ],
    "control_loop_sign_semantic_drift": [
        "restore source control-loop sign or direction before topology edits",
        "limit control-loop repair to injected sign drift and gain inversion first",
        "rerun simulate and compare loop stability before accepting the patch",
    ],
    "mode_switch_guard_logic_error": [
        "restore source guard thresholds and mode switch conditions first",
        "limit guard repair to the injected when/assert block before wider edits",
        "rerun simulate and inspect the mode transition timing before accepting the patch",
    ],
    "cascading_structural_failure": [
        "repair the first exposed structural fault conservatively before widening edits",
        "expect a second failure layer after the first repair and rerun checkModel/simulate immediately",
        "preserve source relationships while addressing cascading faults in sequence",
    ],
    "coupled_conflict_failure": [
        "identify paired source rewrites that must be repaired together",
        "avoid fixing only one side of a coupled conflict before rerunning simulate",
        "rerun simulate after each grouped repair step and inspect the next exposed conflict",
    ],
    "false_friend_patch_trap": [
        "avoid the most local-looking patch if it does not restore the original source relation",
        "prefer grouped source-aligned repairs over isolated trap-friendly edits",
        "rerun simulate after each patch and inspect whether a second-layer failure emerged",
    ],
    "steady_state_target_violation": [
        "restore source gain, height, or steady-state scaling before broader edits",
        "prefer source-aligned parameter repair over topology or declaration changes",
        "rerun simulate and re-check the steady-state target before accepting the patch",
    ],
    "transient_response_contract_violation": [
        "restore source transient-shaping parameters such as width, period, damping, or gain first",
        "prefer localized timing and response repair over broad structural edits",
        "rerun simulate and inspect overshoot and settling behavior before accepting the patch",
    ],
    "mode_transition_contract_violation": [
        "restore source transition timing, threshold, and recovery parameters first",
        "avoid broad edits when the mismatch is localized to mode-transition behavior",
        "rerun simulate and check post-transition recovery before accepting the patch",
    ],
    "param_perturbation_robustness_violation": [
        "shrink over-aggressive gain, scaling, and amplitude values toward a conservative mid-range before broader edits",
        "prefer localized numeric stabilization that remains valid across nearby perturbations",
        "rerun simulate against adjacent parameter scenarios before accepting the patch",
    ],
    "initial_condition_robustness_violation": [
        "smooth start-time, offset, width, period, and initial-condition shaping values toward gentler timings first",
        "prefer localized recovery of initial-condition behavior over broad structural edits or source rollback",
        "rerun simulate against neighboring initial conditions before accepting the patch",
    ],
    "scenario_switch_robustness_violation": [
        "widen the switch timing margin and reduce over-aggressive transition parameters first",
        "prefer fixes that remain valid across adjacent scenario variants, not just the nominal case or a source-text restore",
        "rerun simulate across the scenario set before accepting the patch",
    ],
    "stability_then_behavior": [
        "stabilize gain, height, and timing parameters before broader edits",
        "expect a second behavior-layer failure after the first stabilization step",
        "rerun simulate after each localized numeric repair and inspect the newly exposed stage",
    ],
    "behavior_then_robustness": [
        "restore nominal behavior first using localized numeric changes only",
        "after nominal behavior is restored, re-check neighboring scenarios before accepting the patch",
        "prefer staged parameter repair over one-shot broad edits",
    ],
    "switch_then_recovery": [
        "repair switch timing and trigger parameters before post-switch recovery tuning",
        "expect a second recovery-layer failure once the switch gate is repaired",
        "rerun simulate after each staged repair and inspect the next exposed phase",
    ],
}


def _as_actions(rows: list[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        item = str(row or "").strip()
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _multistep_next_focus(
    *,
    failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
    stage_2_branch: str = "",
    trap_branch: bool = False,
) -> str:
    ftype = str(failure_type or "").strip().lower()
    stage = str(current_stage or "").strip().lower()
    bucket = str(current_fail_bucket or "").strip().lower()
    if stage in {"", "stage_1"}:
        mapping = {
            "stability_then_behavior": "unlock_stage_2_behavior_gate",
            "behavior_then_robustness": "unlock_stage_2_neighbor_robustness_gate",
            "switch_then_recovery": "unlock_stage_2_recovery_gate",
        }
        return mapping.get(ftype, "unlock_stage_2")
    if stage == "stage_2":
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
    if stage == "passed":
        return "stop_editing"
    return "inspect_current_stage"


def _multistep_branch_mode(*, current_stage: str, stage_2_branch: str, preferred_stage_2_branch: str, trap_branch: bool) -> str:
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


def build_multistep_llm_plan_prompt_hints_v1(
    *,
    request_kind: str,
    current_stage: str,
    current_branch: str = "",
    preferred_branch: str = "",
    previous_plan_failed_signal: str = "",
    realism_version: str = "",
    replan_count: int = 0,
    guided_search_observation_available: bool = False,
) -> list[str]:
    kind = str(request_kind or "").strip().lower()
    stage = str(current_stage or "").strip().lower()
    branch = str(current_branch or "").strip().lower()
    preferred = str(preferred_branch or "").strip().lower()
    failed_signal = str(previous_plan_failed_signal or "").strip().lower()
    realism = str(realism_version or "").strip().lower()
    try:
        replan_idx = max(0, int(replan_count))
    except Exception:
        replan_idx = 0
    if kind == "replan":
        return _as_actions(
            [
                "output a new branch-aware repair plan instead of repeating the first-plan parameter direction",
                f"explain why the previous plan failed using the observed signal '{failed_signal or 'no_progress'}'",
                f"if the current branch '{branch or 'unknown'}' looks wrong, explicitly move toward '{preferred or 'the preferred branch'}'",
                "make branch choice explicit: say whether to continue the current branch or switch to a new branch",
                "allocate a small integer budget across branch diagnosis, branch escape, and final resolution",
                "make the budget explicit enough that execution can follow it without guessing",
                "output an explicit guided_search_bucket_sequence using branch_diagnosis, branch_escape, and resolution",
                "favor a minimal backtracking step and a new parameter subset over repeating the previous patch verbatim",
                "name the parameter directions that should be abandoned from the previous failed plan",
                "stop the replan when the preferred branch is restored or when all scenarios pass",
                (
                    "use the structured guided-search observation to avoid reusing buckets that already spent budget without progress"
                    if guided_search_observation_available
                    else ""
                ),
                (
                    "this is a deeper v5-style replan, so compare the current branch against at least one alternative branch "
                    "before keeping the same direction"
                    if realism == "v5" or replan_idx >= 1
                    else ""
                ),
                (
                    "if this is not the first replan, explain why the remaining budget should stay on the current branch or switch away again"
                    if replan_idx >= 1
                    else ""
                ),
            ]
        )
    return _as_actions(
        [
            f"diagnose the current multistep stage '{stage or 'unknown'}' before proposing numeric edits",
            "output a small parameter-direction plan, not full Modelica code",
            f"if a preferred branch exists, keep the plan aligned with '{preferred or branch or 'the preferred branch'}'",
            "use only existing numeric parameters already present in the model text",
            "stop the plan when the current stage is cleared or the branch diagnosis changes",
            (
                "for v5 realism, prefer branch-diagnostic parameter choices that separate competing stage_2 branches instead of immediately spending the full budget on one narrow patch"
                if realism == "v5"
                else ""
            ),
        ]
    )


def _multistep_stage_actions(*, failure_type: str, current_stage: str, next_focus: str) -> list[str]:
    ftype = str(failure_type or "").strip().lower()
    stage = str(current_stage or "").strip().lower()
    focus = str(next_focus or "").strip().lower()
    if stage in {"", "stage_1"}:
        mapping = {
            "stability_then_behavior": [
                "use a bounded local numeric search over stage-1 stability parameters before broad edits",
                "focus only on restoring stability margin and startup timing so the behavior layer can unlock",
                "treat this round as a stage-1 unlock step, not a full behavior repair",
                "avoid behavior-only tuning until the stability gate is cleared",
            ],
            "behavior_then_robustness": [
                "use a bounded local numeric search over stage-1 nominal-behavior parameters before broad edits",
                "focus only on restoring nominal behavior for the primary scenario first",
                "treat this round as a stage-1 unlock step, not a robustness sweep",
                "avoid neighboring-scenario tuning until nominal behavior is restored",
            ],
            "switch_then_recovery": [
                "use a bounded local numeric search over stage-1 switch timing parameters before broad edits",
                "focus only on switch timing and trigger recovery so the post-switch layer can unlock",
                "treat this round as a stage-1 unlock step, not a recovery-tail repair",
                "avoid recovery-tail tuning until the switch gate is cleared",
            ],
        }
        return mapping.get(ftype, [f"focus on {focus.replace('_', ' ')}"])
    if stage == "stage_2":
        mapping = {
            "stability_then_behavior": [
                "use a bounded local numeric search over the exposed stage-2 behavior parameters before broader patches",
                "stage_2 is unlocked: focus only on behavior-layer repair and stop revisiting stability parameters first",
                "prioritize neighboring-scenario behavior consistency over reopening the stage-1 margin fix",
                "reject edits that reintroduce stage-1 instability while addressing the exposed behavior layer",
            ],
            "behavior_then_robustness": [
                "use a bounded local numeric search over the exposed stage-2 robustness parameters before broader patches",
                "stage_2 is unlocked: focus only on neighbor robustness and stop revisiting nominal-behavior unlock parameters",
                "prioritize adjacent-scenario consistency over further stage-1 tuning",
                "reject edits that reopen stage-1 nominal behavior while addressing the exposed robustness layer",
            ],
            "switch_then_recovery": [
                "use a bounded local numeric search over the exposed stage-2 recovery parameters before broader patches",
                "stage_2 is unlocked: focus only on post-switch recovery and stop revisiting switch-gate unlock parameters",
                "prioritize recovery-tail consistency after the switch segment is restored",
                "reject edits that reopen stage-1 switch timing while addressing the exposed recovery layer",
            ],
        }
        return mapping.get(ftype, [f"focus on {focus.replace('_', ' ')}"])
    if stage == "passed":
        return ["all active stages are cleared; do not edit further"]
    return []


def _multistep_branch_actions(*, branch: str, preferred_branch: str) -> list[str]:
    branch_norm = str(branch or "").strip().lower()
    preferred_norm = str(preferred_branch or "").strip().lower()
    mapping = {
        "neighbor_overfit_trap": [
            "treat the current stage-2 branch as a trap and prioritize branch escape before any normal second-layer resolution",
            "revert the overfit direction that favored neighbor-only timing before resuming behavior-layer repair",
            f"stay focused on escaping {branch_norm} back to {preferred_norm or 'the preferred branch'} before broader search",
        ],
        "nominal_overfit_trap": [
            "treat the current stage-2 branch as a trap and prioritize branch escape before any normal second-layer resolution",
            "revert the nominal-only overfit direction before resuming neighbor robustness repair",
            f"stay focused on escaping {branch_norm} back to {preferred_norm or 'the preferred branch'} before broader search",
        ],
        "recovery_overfit_trap": [
            "treat the current stage-2 branch as a trap and prioritize branch escape before any normal second-layer resolution",
            "revert the recovery-overfit direction before resuming post-switch recovery repair",
            f"stay focused on escaping {branch_norm} back to {preferred_norm or 'the preferred branch'} before broader search",
        ],
    }
    return list(mapping.get(branch_norm, []))


def _looks_like_multistep_stage_1_action(*, failure_type: str, action: str) -> bool:
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


def build_multistep_repair_plan_v0(
    *,
    failure_type: str,
    current_stage: str,
    current_fail_bucket: str,
    stage_2_branch: str = "",
    preferred_stage_2_branch: str = "",
    trap_branch: bool = False,
    plan_actions: list[str] | None = None,
) -> dict:
    ftype = str(failure_type or "").strip().lower()
    stage = str(current_stage or "").strip().lower()
    fail_bucket = str(current_fail_bucket or "").strip().lower()
    next_focus = _multistep_next_focus(
        failure_type=ftype,
        current_stage=stage,
        current_fail_bucket=fail_bucket,
        stage_2_branch=stage_2_branch,
        trap_branch=trap_branch,
    )
    branch_mode = _multistep_branch_mode(
        current_stage=stage,
        stage_2_branch=stage_2_branch,
        preferred_stage_2_branch=preferred_stage_2_branch,
        trap_branch=trap_branch,
    )
    actions = _as_actions(plan_actions or [])
    if stage in {"", "stage_1"}:
        goal = {
            "stability_then_behavior": "unlock the second behavior layer by restoring stage-1 stability only",
            "behavior_then_robustness": "unlock the second robustness layer by restoring nominal behavior only",
            "switch_then_recovery": "unlock the second recovery layer by restoring switch timing only",
        }.get(ftype, "unlock stage_2 only")
        constraints = [
            "only edit existing numeric parameters tied to the stage-1 unlock gate",
            "do not spend this round on second-layer cleanup before stage_2 is unlocked",
            "do not change structure, declarations, connectors, or add new parameters",
        ]
        stop_condition = "stop this plan when stage_2_unlocked becomes true"
    elif stage == "stage_2":
        if branch_mode == "trap":
            goal = f"escape trap branch {stage_2_branch or 'stage_2_trap'} and return to {preferred_stage_2_branch or 'the preferred branch'} before normal second-layer resolution"
            constraints = [
                "do not reopen stage-1 parameter clusters unless the task regresses back to stage_1",
                "use trap escape actions before any generic stage_2 resolution search",
                "do not change structure, declarations, connectors, or add new parameters",
            ]
            stop_condition = "stop this branch plan when the task leaves the trap branch, all scenarios pass, or the task regresses back to stage_1"
        else:
            goal = {
                "stability_then_behavior": "resolve the exposed second-stage behavior contract without reopening stage-1 stability",
                "behavior_then_robustness": "resolve the exposed second-stage neighbor robustness layer without reopening stage-1 nominal behavior",
                "switch_then_recovery": "resolve the exposed second-stage post-switch recovery layer without reopening stage-1 switch timing",
            }.get(ftype, "resolve the exposed second layer only")
            constraints = [
                "do not reopen stage-1 parameter clusters unless the task regresses back to stage_1",
                "prioritize the exposed second-layer fail bucket over any first-layer cleanup",
                "do not change structure, declarations, connectors, or add new parameters",
            ]
            stop_condition = "stop this plan when all scenarios pass or the task regresses back to stage_1"
    elif stage == "passed":
        goal = "stop editing because all active stages are cleared"
        constraints = ["do not edit further"]
        stop_condition = "stop immediately"
    else:
        goal = "inspect current stage before editing"
        constraints = ["do not change structure or add new parameters"]
        stop_condition = "stop when stage intent is clarified"
    return {
        "plan_stage": stage,
        "branch_stage": stage if stage == "stage_2" else "",
        "current_branch": str(stage_2_branch or "").strip().lower(),
        "preferred_branch": str(preferred_stage_2_branch or "").strip().lower(),
        "branch_mode": branch_mode,
        "plan_goal": goal,
        "plan_actions": actions,
        "plan_constraints": constraints,
        "plan_stop_condition": stop_condition,
        "next_focus": next_focus,
        "branch_plan_goal": goal if stage == "stage_2" else "",
        "branch_plan_actions": actions if stage == "stage_2" else [],
        "branch_plan_stop_condition": stop_condition if stage == "stage_2" else "",
    }


def recommend_repair_actions_v0(
    *,
    failure_type: str,
    expected_stage: str,
    diagnostic_payload: dict | None = None,
    fallback_actions: list[str] | None = None,
    multistep_context: dict | None = None,
) -> dict:
    ftype = str(failure_type or "").strip().lower()
    stage = str(expected_stage or "").strip().lower()
    diagnostic = diagnostic_payload if isinstance(diagnostic_payload, dict) else {}
    multistep = multistep_context if isinstance(multistep_context, dict) else {}
    suggested = [str(x) for x in (diagnostic.get("suggested_actions") or []) if isinstance(x, str)]
    rules = [str(x) for x in (DEFAULT_RULES.get(ftype) or []) if isinstance(x, str)]
    current_stage = str(multistep.get("current_stage") or "").strip().lower()
    current_fail_bucket = str(multistep.get("current_fail_bucket") or "").strip().lower()
    stage_2_branch = str(multistep.get("stage_2_branch") or "").strip().lower()
    preferred_stage_2_branch = str(multistep.get("preferred_stage_2_branch") or "").strip().lower()
    trap_branch = bool(multistep.get("trap_branch"))
    next_focus = _multistep_next_focus(
        failure_type=ftype,
        current_stage=current_stage,
        current_fail_bucket=current_fail_bucket,
        stage_2_branch=stage_2_branch,
        trap_branch=trap_branch,
    )
    if ftype in {"stability_then_behavior", "behavior_then_robustness", "switch_then_recovery"} and current_stage:
        rules = _multistep_stage_actions(
            failure_type=ftype,
            current_stage=current_stage,
            next_focus=next_focus,
        )
        if current_stage == "stage_2" and trap_branch:
            rules = _multistep_branch_actions(
                branch=stage_2_branch,
                preferred_branch=preferred_stage_2_branch,
            ) + rules

    stage_guard: list[str] = []
    if rules or suggested:
        if stage == "check":
            stage_guard.append("do not simulate until checkModel returns pass")
            if ftype == "underconstrained_system":
                stage_guard.append("do not replace topology restore with broad equation rewrite while checkModel still reports underconstraint")
        elif stage == "simulate":
            stage_guard.append("compile/checkModel must pass before any simulate retry")
    if current_stage == "stage_2":
        stage_guard.append("stage_2 is already unlocked, so do not reopen stage_1 unless the model regresses back to stage_1")
        stage_guard.append("after stage_2 unlock, rank second-layer repair above any first-layer cleanup")
        if trap_branch:
            stage_guard.append("the current stage_2 branch is a trap, so spend the first repair budget on escaping the trap before normal resolution")
            stage_guard.append("do not treat trap escape as optional cleanup; it is the first repair goal for this round")

    deterministic_actions = _as_actions(rules + suggested + stage_guard)
    fallback = _as_actions(fallback_actions or [])
    conflict_rejected_count = 0
    if current_stage == "stage_2" and deterministic_actions:
        filtered_actions: list[str] = []
        for action in deterministic_actions:
            if _looks_like_multistep_stage_1_action(failure_type=ftype, action=action):
                conflict_rejected_count += 1
                continue
            filtered_actions.append(action)
        deterministic_actions = _as_actions(filtered_actions)
    chosen_actions = deterministic_actions if deterministic_actions else fallback
    plan = build_multistep_repair_plan_v0(
        failure_type=ftype,
        current_stage=current_stage,
        current_fail_bucket=current_fail_bucket,
        stage_2_branch=stage_2_branch,
        preferred_stage_2_branch=preferred_stage_2_branch,
        trap_branch=trap_branch,
        plan_actions=chosen_actions,
    ) if current_stage else {}
    plan_followed = bool(current_stage) and bool(chosen_actions)

    if deterministic_actions:
        return {
            "channel": "deterministic_rule_policy",
            "actions": deterministic_actions,
            "fallback_used": False,
            "deterministic_action_count": len(deterministic_actions),
            "fallback_action_count": len(fallback),
            "current_stage": current_stage,
            "next_focus": next_focus,
            "stage_aware": bool(current_stage),
            "plan": plan,
            "plan_generated": bool(current_stage),
            "plan_followed": plan_followed,
            "plan_conflict_rejected": conflict_rejected_count > 0,
            "plan_conflict_rejected_count": conflict_rejected_count,
            "executed_plan_action": chosen_actions[0] if chosen_actions else "",
        }
    return {
        "channel": "fallback_planner_actions",
        "actions": fallback,
        "fallback_used": True,
        "deterministic_action_count": 0,
        "fallback_action_count": len(fallback),
        "current_stage": current_stage,
        "next_focus": next_focus,
        "stage_aware": bool(current_stage),
        "plan": plan,
        "plan_generated": bool(current_stage),
        "plan_followed": plan_followed,
        "plan_conflict_rejected": conflict_rejected_count > 0,
        "plan_conflict_rejected_count": conflict_rejected_count,
        "executed_plan_action": chosen_actions[0] if chosen_actions else "",
    }


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend repair actions using deterministic policy + fallback")
    parser.add_argument("--failure-type", required=True)
    parser.add_argument("--expected-stage", default="")
    parser.add_argument("--diagnostic", default="")
    parser.add_argument("--fallback-actions", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_repair_action_policy_v0/policy.json")
    args = parser.parse_args()

    diagnostic = {}
    if str(args.diagnostic).strip():
        p = Path(str(args.diagnostic))
        if p.exists():
            diagnostic = json.loads(p.read_text(encoding="utf-8"))
    fallback_actions = [x.strip() for x in str(args.fallback_actions or "").split("|") if x.strip()]
    payload = recommend_repair_actions_v0(
        failure_type=str(args.failure_type),
        expected_stage=str(args.expected_stage),
        diagnostic_payload=diagnostic,
        fallback_actions=fallback_actions,
    )
    payload["schema_version"] = "agent_modelica_repair_action_policy_v0"
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_json(args.out, payload)
    print(json.dumps({"status": "PASS", "channel": payload.get("channel"), "action_count": len(payload.get("actions") or [])}))


if __name__ == "__main__":
    main()
