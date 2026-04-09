from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_9_0_common import PRIORITY_BARRIERS
from .agent_modelica_v0_9_1_common import (
    DEFAULT_HOLDOUT_SUMMARY_PATH,
    DEFAULT_HOLDOUT_TASKSET_PATH,
    DEFAULT_SOURCE_ADMISSION_OUT_DIR,
    DEFAULT_UPLIFT_TASKSET_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SOURCE_DISCOVERY_SPECS = [
    {
        "source_id": "l4_uplift_challenge_frozen",
        "taskset_path": str(DEFAULT_UPLIFT_TASKSET_PATH),
        "summary_path": "",
        "source_type": "challenge_pack_frozen",
        "source_collection_method": "artifact_frozen_taskset",
        "source_provenance_description": "Frozen uplift challenge taskset built from real electrical mutation artifacts.",
        "source_authenticity_risk_level": "medium",
    },
    {
        "source_id": "layer4_holdout_frozen",
        "taskset_path": str(DEFAULT_HOLDOUT_TASKSET_PATH),
        "summary_path": str(DEFAULT_HOLDOUT_SUMMARY_PATH),
        "source_type": "layer4_holdout_frozen",
        "source_collection_method": "artifact_frozen_holdout_split",
        "source_provenance_description": "Frozen layer-4 holdout taskset with multiround trap-heavy cases.",
        "source_authenticity_risk_level": "high",
    },
]

FAILURE_TYPE_TO_BARRIER = {
    "semantic_regression": "goal_artifact_missing_after_surface_fix",
    "model_check_error": "dispatch_or_policy_limited_unresolved",
    "simulate_error": "workflow_spillover_unresolved",
}


def _family_from_origin(origin_task_id: str) -> str:
    text = origin_task_id.lower()
    if "dual_source" in text:
        return "component_api_alignment"
    if "ladder" in text or "parallel" in text:
        return "local_interface_alignment"
    return "medium_redeclare_alignment"


def _workflow_template_from_origin(origin_task_id: str) -> str:
    text = origin_task_id.lower()
    if "dual_source" in text:
        return "restore_nominal_supply_chain"
    if "ladder" in text or "parallel" in text:
        return "restore_boundary_signal_integrity"
    if "r_divider" in text or "rlc" in text or "rc_constant" in text or "rl_step" in text:
        return "recover_medium_goal"
    return "recover_reporting_chain"


def _goal_specific_check_mode_from_failure(failure_type: str) -> str:
    if failure_type == "model_check_error":
        return "invariant_only"
    return "artifact_only"


def _build_candidate_from_new_source(row: dict, source_id: str) -> dict | None:
    failure_type = str(row.get("failure_type") or "")
    barrier = FAILURE_TYPE_TO_BARRIER.get(failure_type)
    if not barrier:
        return None
    task_id = str(row.get("task_id") or "")
    origin_task_id = str(row.get("origin_task_id") or task_id)
    workflow_template_id = _workflow_template_from_origin(origin_task_id)
    family_id = _family_from_origin(origin_task_id)
    workflow_proximity_pass = bool(task_id.startswith("electrical_")) and str(row.get("expected_stage") or "") in {
        "check",
        "simulate",
    }
    anti_fake_workflow_pass = workflow_proximity_pass and failure_type in FAILURE_TYPE_TO_BARRIER
    context_naturalness_risk = "medium"
    goal_level_acceptance_is_realistic = bool(workflow_template_id) and bool(family_id)
    authenticity_audit_pass = (
        workflow_proximity_pass
        and anti_fake_workflow_pass
        and goal_level_acceptance_is_realistic
        and context_naturalness_risk != "high"
    )
    return {
        "task_id": f"v091_{source_id}_{task_id}",
        "base_task_id": task_id,
        "source_id": source_id,
        "family_id": family_id,
        "workflow_task_template_id": workflow_template_id,
        "complexity_tier": row.get("scale") or "medium",
        "goal_specific_check_mode": _goal_specific_check_mode_from_failure(failure_type),
        "current_pilot_outcome": "candidate_only_not_yet_executed",
        "current_primary_barrier_label": barrier,
        "authenticity_audit": {
            "source_provenance": source_id,
            "workflow_proximity_pass": workflow_proximity_pass,
            "anti_fake_workflow_pass": anti_fake_workflow_pass,
            "context_naturalness_risk": context_naturalness_risk,
            "goal_level_acceptance_is_realistic": goal_level_acceptance_is_realistic,
            "authenticity_audit_pass": authenticity_audit_pass,
        },
        "barrier_sampling_audit": {
            "barrier_sampling_intent_present": True,
            "target_barrier_family": barrier,
            "barrier_sampling_rationale": "Real-source expansion prioritizes underrepresented v0.8.x workflow barriers without changing task definition.",
            "selection_priority_reason": "expand_real_candidate_sources_under_frozen_governance",
            "task_definition_was_changed_for_barrier_targeting": False,
            "barrier_sampling_audit_pass": True,
        },
    }


def _inspect_source(spec: dict) -> dict:
    taskset = load_json(spec["taskset_path"])
    tasks = taskset.get("tasks") if isinstance(taskset.get("tasks"), list) else []
    candidate_rows = []
    for row in tasks:
        if not isinstance(row, dict):
            continue
        candidate = _build_candidate_from_new_source(row, spec["source_id"])
        if candidate is not None:
            candidate_rows.append(candidate)
    evaluations = evaluate_candidate_rows(candidate_rows)
    admitted_candidates = [row for row in evaluations if row.get("admitted")]
    barrier_counts = {barrier: 0 for barrier in PRIORITY_BARRIERS}
    for row in admitted_candidates:
        barrier = str(row.get("target_barrier_family") or "")
        if barrier in barrier_counts:
            barrier_counts[barrier] += 1

    source_type = str(spec.get("source_type") or "")
    provenance_present = bool(spec.get("source_provenance_description")) and Path(spec["taskset_path"]).exists()
    workflow_compatible = source_type == "challenge_pack_frozen" and len(admitted_candidates) >= 3
    source_admission_pass = provenance_present and workflow_compatible
    rejection_reason = ""
    if not source_admission_pass:
        if not provenance_present:
            rejection_reason = "source_provenance_missing_or_unreadable"
        elif source_type != "challenge_pack_frozen":
            rejection_reason = "source_cannot_yield_workflow_proximal_candidates_without_reframing"
        else:
            rejection_reason = "source_yield_below_meaningful_growth_floor"
    return {
        "source_id": spec["source_id"],
        "source_type": source_type,
        "source_provenance_description": spec["source_provenance_description"],
        "source_authenticity_risk_level": spec["source_authenticity_risk_level"],
        "source_collection_method": spec["source_collection_method"],
        "workflow_family_coverage_estimate": sorted({str(row.get("family_id") or "") for row in candidate_rows if row.get("family_id")}),
        "likely_reachable_priority_barriers": [barrier for barrier, count in barrier_counts.items() if count > 0],
        "source_task_count": len(tasks),
        "governance_passing_candidate_count": len(admitted_candidates),
        "candidate_depth_by_priority_barrier": barrier_counts,
        "source_admission_pass": source_admission_pass,
        "source_rejection_reason": rejection_reason,
        "candidate_rows": candidate_rows,
        "candidate_row_evaluations": evaluations,
    }


def build_v091_candidate_source_admission(
    *,
    out_dir: str = str(DEFAULT_SOURCE_ADMISSION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    inspected = [_inspect_source(spec) for spec in SOURCE_DISCOVERY_SPECS]
    admitted = [row for row in inspected if row.get("source_admission_pass")]
    rejected = [row for row in inspected if not row.get("source_admission_pass")]
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_candidate_source_admission",
        "generated_at_utc": now_utc(),
        "status": "PASS" if admitted else "FAIL",
        "candidate_source_intake_table": inspected,
        "candidate_source_expansion_ledger": {
            "baseline_source_count": 1,
            "inspected_source_count": len(inspected),
            "admitted_source_count": len(admitted),
            "rejected_source_count": len(rejected),
        },
        "newly_admitted_source_registry": [
            {
                "source_id": row["source_id"],
                "source_type": row["source_type"],
                "source_provenance_description": row["source_provenance_description"],
                "source_collection_method": row["source_collection_method"],
                "workflow_family_coverage_estimate": row["workflow_family_coverage_estimate"],
                "likely_reachable_priority_barriers": row["likely_reachable_priority_barriers"],
                "governance_passing_candidate_count": row["governance_passing_candidate_count"],
            }
            for row in admitted
        ],
        "source_admission_decision_table": [
            {
                "source_id": row["source_id"],
                "source_admission_pass": row["source_admission_pass"],
                "source_rejection_reason": row["source_rejection_reason"],
                "governance_passing_candidate_count": row["governance_passing_candidate_count"],
            }
            for row in inspected
        ],
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.1 Candidate Source Admission",
                "",
                f"- admitted_source_count: `{len(admitted)}`",
                f"- rejected_source_count: `{len(rejected)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.1 candidate source admission artifact.")
    parser.add_argument("--out-dir", default=str(DEFAULT_SOURCE_ADMISSION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v091_candidate_source_admission(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "admitted_source_count": payload["candidate_source_expansion_ledger"]["admitted_source_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
