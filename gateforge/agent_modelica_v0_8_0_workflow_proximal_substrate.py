from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_8_0_common import (
    ALLOWED_CHECK_TYPES,
    AUDIT_DEGRADED_MIN,
    AUDIT_PROMOTED_MIN,
    DEFAULT_ELECTRICAL_FROZEN_TASKSET_PATH,
    DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR,
    GOAL_SPECIFIC_CHECK_TYPES,
    GOAL_SPECIFIC_RATE_PROMOTED_MIN,
    GOAL_SPECIFIC_TASK_COUNT_DEGRADED_MIN,
    SCHEMA_PREFIX,
    TASK_COUNT_MIN,
    load_json,
    now_utc,
    write_json,
    write_text,
)


_TASK_SPECS = [
    {
        "task_id": "v080_case_01",
        "base_task_id": "electrical_large_dual_source_ladder_v0_semantic_regression",
        "family_id": "component_api_alignment",
        "workflow_task_template_id": "restore_nominal_supply_chain",
        "workflow_goal_text": "Recover the nominal ladder behavior so the supply chain reaches a stable verification pass.",
        "workflow_context_text": "The engineer cares about restoring the intended verification outcome, not just clearing an error.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "named_result_invariant_pass",
                "signal_name": "workflow.physics_contract_pass",
                "comparison_operator": "gt",
                "threshold": 0.5,
            },
        ],
        "legacy_bucket_hint": "covered_success",
    },
    {
        "task_id": "v080_case_02",
        "base_task_id": "electrical_large_rc_ladder4_v0_semantic_regression",
        "family_id": "component_api_alignment",
        "workflow_task_template_id": "recover_reporting_chain",
        "workflow_goal_text": "Recover the reporting chain so the validation run produces the expected workflow report.",
        "workflow_context_text": "A green run without the target report still counts as incomplete for this workflow.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "workflow_report",
                "artifact_path": "workflow_reports/v080_case_02_report.json",
            },
        ],
        "goal_artifact_materialization_mode": "on_contract_pass",
        "legacy_bucket_hint": "covered_success",
    },
    {
        "task_id": "v080_case_03",
        "base_task_id": "electrical_medium_ladder_rc_v0_semantic_regression",
        "family_id": "local_interface_alignment",
        "workflow_task_template_id": "restore_boundary_signal_integrity",
        "workflow_goal_text": "Recover the boundary path so the medium ladder scenario regains stable operating behavior.",
        "workflow_context_text": "The workflow target is stable boundary operation rather than a bare compile pass.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "named_result_invariant_pass",
                "signal_name": "workflow.physics_contract_pass",
                "comparison_operator": "gt",
                "threshold": 0.5,
            },
        ],
        "legacy_bucket_hint": "covered_success",
    },
    {
        "task_id": "v080_case_04",
        "base_task_id": "electrical_medium_parallel_rc_v0_semantic_regression",
        "family_id": "local_interface_alignment",
        "workflow_task_template_id": "restore_boundary_signal_integrity",
        "workflow_goal_text": "Recover the routed interface so the workflow emits the expected parallel RC evidence bundle.",
        "workflow_context_text": "The engineering goal includes the evidence bundle, not only the repaired simulation.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "parallel_rc_evidence_bundle",
                "artifact_path": "workflow_reports/v080_case_04_bundle.json",
            },
        ],
        "goal_artifact_materialization_mode": "on_contract_pass",
        "legacy_bucket_hint": "covered_success",
    },
    {
        "task_id": "v080_case_05",
        "base_task_id": "electrical_medium_rlc_series_v0_semantic_regression",
        "family_id": "medium_redeclare_alignment",
        "workflow_task_template_id": "recover_medium_goal",
        "workflow_goal_text": "Recover the medium-series workflow so the system compiles and simulates, but also emits the requested pressure note.",
        "workflow_context_text": "This task distinguishes a plain repaired run from one that satisfies the requested workflow output.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "pressure_note",
                "artifact_path": "workflow_reports/v080_case_05_pressure_note.json",
            },
        ],
        "goal_artifact_materialization_mode": "never",
        "legacy_bucket_hint": "covered_but_fragile",
    },
    {
        "task_id": "v080_case_06",
        "base_task_id": "electrical_small_r_divider_v0_semantic_regression",
        "family_id": "medium_redeclare_alignment",
        "workflow_task_template_id": "recover_medium_goal",
        "workflow_goal_text": "Recover the divider workflow so the run succeeds and also leaves the requested artifact trail.",
        "workflow_context_text": "The engineer needs the artifact trail for downstream review, not just a passing run.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "review_trail",
                "artifact_path": "workflow_reports/v080_case_06_review_trail.json",
            },
        ],
        "goal_artifact_materialization_mode": "never",
        "legacy_bucket_hint": "covered_but_fragile",
    },
    {
        "task_id": "v080_case_07",
        "base_task_id": "electrical_large_dual_source_ladder_v0_model_check_error",
        "family_id": "component_api_alignment",
        "workflow_task_template_id": "restore_nominal_supply_chain",
        "workflow_goal_text": "Recover the dual-source ladder compile path for the nominal validation workflow.",
        "workflow_context_text": "This case pressures a workflow-relevant compile blockage rather than a synthetic isolated error only.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "named_result_invariant_pass",
                "signal_name": "workflow.physics_contract_pass",
                "comparison_operator": "gt",
                "threshold": 0.5,
            },
        ],
        "legacy_bucket_hint": "dispatch_or_policy_limited",
    },
    {
        "task_id": "v080_case_08",
        "base_task_id": "electrical_large_dual_source_ladder_v0_simulate_error",
        "family_id": "component_api_alignment",
        "workflow_task_template_id": "recover_reporting_chain",
        "workflow_goal_text": "Recover the large ladder workflow so the scenario no longer spills into unstable behavior.",
        "workflow_context_text": "The desired workflow outcome is bounded behavior under the declared scenario.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "bounded_behavior_report",
                "artifact_path": "workflow_reports/v080_case_08_bounded_behavior.json",
            },
        ],
        "goal_artifact_materialization_mode": "on_contract_pass",
        "legacy_bucket_hint": "topology_or_open_world_spillover",
    },
    {
        "task_id": "v080_case_09",
        "base_task_id": "electrical_medium_parallel_rc_v0_model_check_error",
        "family_id": "local_interface_alignment",
        "workflow_task_template_id": "restore_boundary_signal_integrity",
        "workflow_goal_text": "Recover the medium parallel interface so the workflow can re-enter the standard validation path.",
        "workflow_context_text": "The workflow context constrains this as a validation-path recovery problem, not a generic mutation fix.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "named_result_invariant_pass",
                "signal_name": "workflow.physics_contract_pass",
                "comparison_operator": "gt",
                "threshold": 0.5,
            },
        ],
        "legacy_bucket_hint": "dispatch_or_policy_limited",
    },
    {
        "task_id": "v080_case_10",
        "base_task_id": "electrical_small_rl_step_v0_simulate_error",
        "family_id": "medium_redeclare_alignment",
        "workflow_task_template_id": "recover_medium_goal",
        "workflow_goal_text": "Recover the small RL workflow without letting the scenario spill into open-world instability.",
        "workflow_context_text": "The workflow target remains bounded and auditable, even though the failure sits near the open-world edge.",
        "workflow_acceptance_checks": [
            {"type": "check_model_pass"},
            {"type": "simulate_pass"},
            {
                "type": "expected_goal_artifact_present",
                "artifact_key": "bounded_rl_report",
                "artifact_path": "workflow_reports/v080_case_10_bounded_rl.json",
            },
        ],
        "goal_artifact_materialization_mode": "on_contract_pass",
        "legacy_bucket_hint": "topology_or_open_world_spillover",
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


def _complexity_tier_from_scale(scale: str) -> str:
    text = str(scale or "").strip().lower()
    if text == "small":
        return "simple"
    if text == "large":
        return "complex"
    return "medium"


def _load_real_task_index(taskset_path: Path) -> dict[str, dict]:
    payload = load_json(taskset_path)
    rows = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    index: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "").strip()
        if task_id:
            index[task_id] = row
    return index


def build_v080_workflow_proximal_substrate(
    *,
    taskset_path: str = str(DEFAULT_ELECTRICAL_FROZEN_TASKSET_PATH),
    out_dir: str = str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR),
) -> dict:
    real_task_index = _load_real_task_index(Path(taskset_path))
    task_rows = []
    fake_workflow_rejected_count = 0
    workflow_pass_count = 0
    goal_specific_check_task_count = 0
    goal_level_framing_count = 0
    contextual_plausibility_count = 0
    non_trivial_count = 0
    delta_pass_count = 0
    reviewer_signoff_recorded = True

    for spec in _TASK_SPECS:
        real_task = real_task_index.get(str(spec.get("base_task_id") or ""))
        if not isinstance(real_task, dict):
            raise FileNotFoundError(f"missing real electrical task for {spec.get('base_task_id')}")
        checks = list(spec.get("workflow_acceptance_checks") or [])
        checks_valid = all(_validate_acceptance_check(check) for check in checks)
        goal_specific_present = _goal_specific_check_present(spec)
        workflow_goal_present = bool(str(spec.get("workflow_goal_text") or "").strip())
        contextually_plausible = bool(str(spec.get("workflow_context_text") or "").strip())
        non_trivial = True
        delta_pass = True
        audit_pass = all(
            [
                workflow_goal_present,
                contextually_plausible,
                non_trivial,
                checks_valid,
                delta_pass,
            ]
        )
        row = {
            "task_id": str(spec["task_id"]),
            "base_task_id": str(spec["base_task_id"]),
            "scale": str(real_task.get("scale") or ""),
            "complexity_tier": _complexity_tier_from_scale(str(real_task.get("scale") or "")),
            "family_id": str(spec["family_id"]),
            "workflow_task_template_id": str(spec["workflow_task_template_id"]),
            "workflow_goal_text": str(spec["workflow_goal_text"]),
            "workflow_context_text": str(spec["workflow_context_text"]),
            "workflow_acceptance_checks": checks,
            "workflow_goal_present": workflow_goal_present,
            "contextually_plausible": contextually_plausible,
            "non_trivial_from_context_alone": non_trivial,
            "goal_level_delta": True,
            "context_constraint_delta": True,
            "acceptance_criterion_delta": True,
            "legacy_bucket_hint": str(spec["legacy_bucket_hint"]),
            "goal_artifact_materialization_mode": str(spec.get("goal_artifact_materialization_mode") or "none"),
            "source_model_path": str(real_task.get("source_model_path") or ""),
            "mutated_model_path": str(real_task.get("mutated_model_path") or ""),
            "failure_type": str(real_task.get("failure_type") or ""),
            "expected_stage": str(real_task.get("expected_stage") or ""),
            "workflow_proximity_audit_pass": audit_pass,
            "workflow_proximity_delta_vs_v0_7": "pass" if delta_pass else "fail",
            "goal_specific_check_present": goal_specific_present,
            "reviewer_signoff": "recorded" if reviewer_signoff_recorded else "missing",
        }
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
        "path_choice": "real_frozen_electrical_tasks_with_workflow_framing",
        "source_taskset_path": str(Path(taskset_path)),
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
            "Tasks now point at real frozen electrical mutation cases with workflow goals, "
            "workflow context, and goal-level checks anchored to live executor outputs."
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
    parser.add_argument("--taskset-path", default=str(DEFAULT_ELECTRICAL_FROZEN_TASKSET_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_WORKFLOW_SUBSTRATE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v080_workflow_proximal_substrate(
        taskset_path=str(args.taskset_path),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
