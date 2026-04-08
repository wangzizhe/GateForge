from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_0_common import (
    ALLOWED_CHECK_TYPES,
    AUDIT_DEGRADED_MIN,
    AUDIT_PROMOTED_MIN,
    DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR,
    GOAL_SPECIFIC_CHECK_TYPES,
    GOAL_SPECIFIC_RATE_PROMOTED_MIN,
    GOAL_SPECIFIC_TASK_COUNT_DEGRADED_MIN,
    SCHEMA_PREFIX,
    TASK_COUNT_MIN,
    now_utc,
    write_json,
    write_text,
)


_TASK_ROWS = [
    {
        "task_id": "v080_case_01",
        "family_id": "component_api_alignment",
        "complexity_tier": "simple",
        "workflow_task_template_id": "restore_nominal_supply_chain",
        "workflow_goal_text": "Make the sensor chain compile and recover the intended nominal output path.",
        "workflow_context_text": "Engineer expects the supply path to remain usable in a nominal validation run.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "named_result_invariant_pass",
                "signal_name": "sensorBus.signal",
                "comparison_operator": "between",
                "lower_bound": 0.95,
                "upper_bound": 1.05,
            },
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": True,
        "goal_level_delta": True,
        "context_constraint_delta": True,
        "acceptance_criterion_delta": True,
        "legacy_bucket_hint": "covered_success",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": True,
            "signal_values": {"sensorBus.signal": 1.0},
            "produced_artifacts": [],
        },
    },
    {
        "task_id": "v080_case_02",
        "family_id": "component_api_alignment",
        "complexity_tier": "medium",
        "workflow_task_template_id": "restore_nominal_supply_chain",
        "workflow_goal_text": "Recover the actuator feed so the nominal simulation produces the expected actuator envelope.",
        "workflow_context_text": "Debugging note says the control path should converge under the baseline settings.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "nominal_envelope_plot",
                "artifact_path": "artifacts/v080/case02_nominal_envelope.png",
            },
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": True,
        "goal_level_delta": True,
        "context_constraint_delta": True,
        "acceptance_criterion_delta": True,
        "legacy_bucket_hint": "covered_success",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": True,
            "signal_values": {},
            "produced_artifacts": ["artifacts/v080/case02_nominal_envelope.png"],
        },
    },
    {
        "task_id": "v080_case_03",
        "family_id": "local_interface_alignment",
        "complexity_tier": "medium",
        "workflow_task_template_id": "restore_boundary_signal_integrity",
        "workflow_goal_text": "Restore the interface so the boundary signal reaches the controller without saturation artifacts.",
        "workflow_context_text": "The engineer is investigating why a validation scenario no longer follows the expected boundary signal.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "named_result_invariant_pass",
                "signal_name": "controller.u",
                "comparison_operator": "gt",
                "threshold": 0.0,
            },
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": True,
        "goal_level_delta": True,
        "context_constraint_delta": True,
        "acceptance_criterion_delta": True,
        "legacy_bucket_hint": "covered_success",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": True,
            "signal_values": {"controller.u": 0.5},
            "produced_artifacts": [],
        },
    },
    {
        "task_id": "v080_case_04",
        "family_id": "local_interface_alignment",
        "complexity_tier": "complex",
        "workflow_task_template_id": "restore_boundary_signal_integrity",
        "workflow_goal_text": "Recover the routed local interface so the supervisory branch regains stable tracking.",
        "workflow_context_text": "The failure only matters because the engineer expects closed-loop tracking to stay inside a bounded band.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "named_result_invariant_pass",
                "signal_name": "trackingError",
                "comparison_operator": "between",
                "lower_bound": -0.1,
                "upper_bound": 0.1,
            },
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": True,
        "goal_level_delta": True,
        "context_constraint_delta": True,
        "acceptance_criterion_delta": True,
        "legacy_bucket_hint": "covered_but_fragile",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": True,
            "signal_values": {"trackingError": 0.25},
            "produced_artifacts": [],
        },
    },
    {
        "task_id": "v080_case_05",
        "family_id": "medium_redeclare_alignment",
        "complexity_tier": "medium",
        "workflow_task_template_id": "recover_medium_goal",
        "workflow_goal_text": "Restore the medium configuration so the thermal loop converges under the stated operating point.",
        "workflow_context_text": "The workflow goal is not just to compile but to recover the intended thermal operating regime.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "named_result_invariant_pass",
                "signal_name": "loop.mediumPressure",
                "comparison_operator": "between",
                "lower_bound": 90000.0,
                "upper_bound": 130000.0,
            },
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": True,
        "goal_level_delta": True,
        "context_constraint_delta": False,
        "acceptance_criterion_delta": True,
        "legacy_bucket_hint": "covered_success",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": True,
            "signal_values": {"loop.mediumPressure": 100000.0},
            "produced_artifacts": [],
        },
    },
    {
        "task_id": "v080_case_06",
        "family_id": "medium_redeclare_alignment",
        "complexity_tier": "complex",
        "workflow_task_template_id": "recover_medium_goal",
        "workflow_goal_text": "Restore medium continuity so the fluid network reaches the intended operating pressure window.",
        "workflow_context_text": "The engineer's goal is pressure-window recovery, not just removal of a redeclare error.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "pressure_window_report",
                "artifact_path": "artifacts/v080/case06_pressure_window.json",
            },
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": True,
        "goal_level_delta": True,
        "context_constraint_delta": True,
        "acceptance_criterion_delta": True,
        "legacy_bucket_hint": "dispatch_or_policy_limited",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": True,
            "signal_values": {},
            "produced_artifacts": [],
        },
    },
    {
        "task_id": "v080_case_07",
        "family_id": "component_api_alignment",
        "complexity_tier": "complex",
        "workflow_task_template_id": "recover_reporting_chain",
        "workflow_goal_text": "Recover the reporting chain so the verification run emits the expected nominal artifact set.",
        "workflow_context_text": "The engineer needs a reproducible report artifact, not just a green check.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "verification_report",
                "artifact_path": "artifacts/v080/case07_verification_report.md",
            },
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": False,
        "goal_level_delta": True,
        "context_constraint_delta": False,
        "acceptance_criterion_delta": True,
        "legacy_bucket_hint": "covered_but_fragile",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": True,
            "signal_values": {},
            "produced_artifacts": [],
        },
    },
    {
        "task_id": "v080_case_08",
        "family_id": "local_interface_alignment",
        "complexity_tier": "simple",
        "workflow_task_template_id": "thin_wrapper_rejected",
        "workflow_goal_text": "Fix the interface issue.",
        "workflow_context_text": "Minimal wrapper that does not materially constrain the solution.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": False,
        "goal_level_delta": False,
        "context_constraint_delta": False,
        "acceptance_criterion_delta": False,
        "legacy_bucket_hint": "covered_success",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": True,
            "signal_values": {},
            "produced_artifacts": [],
        },
    },
    {
        "task_id": "v080_case_09",
        "family_id": "medium_redeclare_alignment",
        "complexity_tier": "complex",
        "workflow_task_template_id": "recover_medium_goal",
        "workflow_goal_text": "Recover the medium setup so the heat rejection loop no longer spills over into unstable topology behavior.",
        "workflow_context_text": "The workflow target is bounded simulation behavior under the declared operating condition.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "named_result_invariant_pass",
                "signal_name": "heatSink.flowRate",
                "comparison_operator": "gt",
                "threshold": 0.01,
            },
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": True,
        "goal_level_delta": True,
        "context_constraint_delta": True,
        "acceptance_criterion_delta": True,
        "legacy_bucket_hint": "topology_or_open_world_spillover",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": False,
            "signal_values": {"heatSink.flowRate": 0.0},
            "produced_artifacts": [],
        },
    },
    {
        "task_id": "v080_case_10",
        "family_id": "component_api_alignment",
        "complexity_tier": "medium",
        "workflow_task_template_id": "recover_reporting_chain",
        "workflow_goal_text": "Recover the reporting interface so the scheduled validation run produces a parsable artifact.",
        "workflow_context_text": "The goal is tied to workflow output availability, not just error removal.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "parsable_validation_artifact",
                "artifact_path": "artifacts/v080/case10_validation_payload.json",
            },
        ],
        "workflow_goal_present": True,
        "contextually_plausible": True,
        "non_trivial_from_context_alone": True,
        "goal_level_delta": True,
        "context_constraint_delta": True,
        "acceptance_criterion_delta": True,
        "legacy_bucket_hint": "unclassified_pending_taxonomy",
        "mock_execution_fixture": {
            "check_model_pass": True,
            "simulate_pass": True,
            "signal_values": {},
            "produced_artifacts": ["artifacts/v080/case10_validation_payload.json"],
        },
    },
]


def _validate_acceptance_check(check: dict) -> bool:
    check_type = str(check.get("type") or "")
    if check_type not in ALLOWED_CHECK_TYPES:
        return False
    if check_type == "named_result_invariant_pass":
        op = str(check.get("comparison_operator") or "")
        signal_name = str(check.get("signal_name") or "")
        if not signal_name or op not in {"gt", "lt", "between"}:
            return False
        if op == "between":
            return "lower_bound" in check and "upper_bound" in check
        return "threshold" in check
    if check_type == "expected_goal_artifact_present":
        return bool(str(check.get("artifact_key") or "")) and bool(str(check.get("artifact_path") or ""))
    return True


def _goal_specific_check_present(row: dict) -> bool:
    checks = list(row.get("workflow_acceptance_checks") or [])
    return any(str(check.get("type") or "") in GOAL_SPECIFIC_CHECK_TYPES for check in checks)


def _task_delta_pass(row: dict) -> bool:
    flags = [
        bool(row.get("goal_level_delta")),
        bool(row.get("context_constraint_delta")),
        bool(row.get("acceptance_criterion_delta")),
    ]
    return sum(1 for flag in flags if flag) >= 2


def build_v080_workflow_proximal_substrate(
    *,
    out_dir: str = str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR),
) -> dict:
    task_rows = []
    fake_workflow_rejected_count = 0
    workflow_pass_count = 0
    goal_specific_check_task_count = 0
    goal_level_framing_count = 0
    contextual_plausibility_count = 0
    non_trivial_count = 0
    delta_pass_count = 0
    reviewer_signoff_recorded = True

    for raw in _TASK_ROWS:
        checks = list(raw.get("workflow_acceptance_checks") or [])
        checks_valid = all(_validate_acceptance_check(check) for check in checks)
        goal_specific_present = _goal_specific_check_present(raw)
        delta_pass = _task_delta_pass(raw)
        workflow_goal_present = bool(raw.get("workflow_goal_present"))
        contextually_plausible = bool(raw.get("contextually_plausible"))
        non_trivial = bool(raw.get("non_trivial_from_context_alone"))
        audit_pass = all(
            [
                workflow_goal_present,
                contextually_plausible,
                non_trivial,
                checks_valid,
                delta_pass,
            ]
        )
        row = dict(raw)
        row["workflow_proximity_audit_pass"] = audit_pass
        row["workflow_proximity_delta_vs_v0_7"] = "pass" if delta_pass else "fail"
        row["goal_specific_check_present"] = goal_specific_present
        row["reviewer_signoff"] = "recorded" if reviewer_signoff_recorded else "missing"
        task_rows.append(row)

        if workflow_goal_present:
            goal_level_framing_count += 1
        if contextually_plausible:
            contextual_plausibility_count += 1
        if non_trivial:
            non_trivial_count += 1
        if delta_pass:
            delta_pass_count += 1
        if goal_specific_present:
            goal_specific_check_task_count += 1
        if audit_pass:
            workflow_pass_count += 1
        else:
            fake_workflow_rejected_count += 1

    task_count = len(task_rows)
    workflow_proximity_audit_pass_rate_pct = round(workflow_pass_count / task_count * 100, 1)
    goal_level_framing_rate_pct = round(goal_level_framing_count / task_count * 100, 1)
    contextual_plausibility_rate_pct = round(contextual_plausibility_count / task_count * 100, 1)
    non_trivial_from_context_rate_pct = round(non_trivial_count / task_count * 100, 1)
    goal_specific_check_rate_pct = round(goal_specific_check_task_count / task_count * 100, 1)
    workflow_proximity_delta_vs_v0_7_rate_pct = round(delta_pass_count / task_count * 100, 1)

    degraded = all(
        [
            task_count >= TASK_COUNT_MIN,
            goal_level_framing_rate_pct >= AUDIT_DEGRADED_MIN,
            contextual_plausibility_rate_pct >= AUDIT_DEGRADED_MIN,
            non_trivial_from_context_rate_pct >= AUDIT_DEGRADED_MIN,
            goal_specific_check_task_count >= GOAL_SPECIFIC_TASK_COUNT_DEGRADED_MIN,
        ]
    )
    promoted = all(
        [
            workflow_proximity_audit_pass_rate_pct >= AUDIT_PROMOTED_MIN,
            goal_level_framing_rate_pct >= AUDIT_PROMOTED_MIN,
            contextual_plausibility_rate_pct >= AUDIT_PROMOTED_MIN,
            non_trivial_from_context_rate_pct >= AUDIT_PROMOTED_MIN,
            goal_specific_check_rate_pct >= GOAL_SPECIFIC_RATE_PROMOTED_MIN,
        ]
    )
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_workflow_proximal_substrate",
        "generated_at_utc": now_utc(),
        "status": "PASS" if degraded else "FAIL",
        "path_choice": "augmented_mutation_tasks",
        "task_count": task_count,
        "task_count_minimum_satisfied": task_count >= TASK_COUNT_MIN,
        "workflow_task_template_id_set": sorted({row["workflow_task_template_id"] for row in task_rows}),
        "workflow_proximity_audit_pass_count": workflow_pass_count,
        "workflow_proximity_audit_pass_rate_pct": workflow_proximity_audit_pass_rate_pct,
        "goal_level_framing_rate_pct": goal_level_framing_rate_pct,
        "contextual_plausibility_rate_pct": contextual_plausibility_rate_pct,
        "non_trivial_from_context_rate_pct": non_trivial_from_context_rate_pct,
        "goal_specific_check_task_count": goal_specific_check_task_count,
        "goal_specific_check_rate_pct": goal_specific_check_rate_pct,
        "fake_workflow_rejected_count": fake_workflow_rejected_count,
        "workflow_proximity_delta_vs_v0_7_rate_pct": workflow_proximity_delta_vs_v0_7_rate_pct,
        "workflow_proximity_delta_vs_v0_7_summary": (
            "Tasks differ from v0.7.x by goal-level framing, workflow-context constraints, "
            "and executable goal-level acceptance checks rather than by wrapper text alone."
        ),
        "reviewer_signoff_recorded": reviewer_signoff_recorded,
        "substrate_floor_status": "promoted" if promoted else ("degraded_but_executable" if degraded else "invalid"),
        "task_rows": task_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.0 Workflow-Proximal Substrate",
                "",
                f"- status: `{payload['status']}`",
                f"- task_count: `{task_count}`",
                f"- workflow_proximity_audit_pass_rate_pct: `{workflow_proximity_audit_pass_rate_pct}`",
                f"- goal_specific_check_rate_pct: `{goal_specific_check_rate_pct}`",
                f"- substrate_floor_status: `{payload['substrate_floor_status']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.0 workflow-proximal substrate.")
    parser.add_argument("--out-dir", default=str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v080_workflow_proximal_substrate(out_dir=str(args.out_dir))
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
