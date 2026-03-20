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


def recommend_repair_actions_v0(
    *,
    failure_type: str,
    expected_stage: str,
    diagnostic_payload: dict | None = None,
    fallback_actions: list[str] | None = None,
) -> dict:
    ftype = str(failure_type or "").strip().lower()
    stage = str(expected_stage or "").strip().lower()
    diagnostic = diagnostic_payload if isinstance(diagnostic_payload, dict) else {}
    suggested = [str(x) for x in (diagnostic.get("suggested_actions") or []) if isinstance(x, str)]
    rules = [str(x) for x in (DEFAULT_RULES.get(ftype) or []) if isinstance(x, str)]

    stage_guard: list[str] = []
    if rules or suggested:
        if stage == "check":
            stage_guard.append("do not simulate until checkModel returns pass")
            if ftype == "underconstrained_system":
                stage_guard.append("do not replace topology restore with broad equation rewrite while checkModel still reports underconstraint")
        elif stage == "simulate":
            stage_guard.append("compile/checkModel must pass before any simulate retry")

    deterministic_actions = _as_actions(rules + suggested + stage_guard)
    fallback = _as_actions(fallback_actions or [])

    if deterministic_actions:
        return {
            "channel": "deterministic_rule_policy",
            "actions": deterministic_actions,
            "fallback_used": False,
            "deterministic_action_count": len(deterministic_actions),
            "fallback_action_count": len(fallback),
        }
    return {
        "channel": "fallback_planner_actions",
        "actions": fallback,
        "fallback_used": True,
        "deterministic_action_count": 0,
        "fallback_action_count": len(fallback),
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
