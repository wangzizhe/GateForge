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


def _multistep_next_focus(*, failure_type: str, current_stage: str, current_fail_bucket: str) -> str:
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
        mapping = {
            "behavior_contract_miss": "resolve_stage_2_behavior_contract",
            "single_case_only": "resolve_stage_2_neighbor_robustness",
            "post_switch_recovery_miss": "resolve_stage_2_post_switch_recovery",
        }
        return mapping.get(bucket, "resolve_stage_2_exposed_failure")
    if stage == "passed":
        return "stop_editing"
    return "inspect_current_stage"


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
    plan_actions: list[str] | None = None,
) -> dict:
    ftype = str(failure_type or "").strip().lower()
    stage = str(current_stage or "").strip().lower()
    fail_bucket = str(current_fail_bucket or "").strip().lower()
    next_focus = _multistep_next_focus(
        failure_type=ftype,
        current_stage=stage,
        current_fail_bucket=fail_bucket,
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
        "plan_goal": goal,
        "plan_actions": actions,
        "plan_constraints": constraints,
        "plan_stop_condition": stop_condition,
        "next_focus": next_focus,
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
    next_focus = _multistep_next_focus(
        failure_type=ftype,
        current_stage=current_stage,
        current_fail_bucket=current_fail_bucket,
    )
    if ftype in {"stability_then_behavior", "behavior_then_robustness", "switch_then_recovery"} and current_stage:
        rules = _multistep_stage_actions(
            failure_type=ftype,
            current_stage=current_stage,
            next_focus=next_focus,
        )

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
