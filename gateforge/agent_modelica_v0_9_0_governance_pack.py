from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_0_common import (
    CONTEXT_NATURALNESS_RISK_VALUES,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEFAULT_V080_CLOSEOUT_PATH,
    DEFAULT_V081_CLOSEOUT_PATH,
    PRIORITY_BARRIERS,
    SCHEMA_PREFIX,
    WORKING_MINIMUM_PER_PRIORITY_BARRIER,
    load_json,
    now_utc,
    write_json,
    write_text,
)


CANDIDATE_SOURCE_REGISTRY = [
    {
        "source_id": "v080_real_frozen_workflow_proximal_substrate",
        "source_type": "real_frozen_workflow_taskset",
        "provenance_description": "v0.8.0 frozen workflow-proximal substrate built from real electrical mutation tasks and live GateForge workflow framing.",
        "authenticity_risk_level": "low",
        "eligible_workflow_families": [
            "component_api_alignment",
            "local_interface_alignment",
            "medium_redeclare_alignment",
        ],
        "likely_reachable_priority_barriers": list(PRIORITY_BARRIERS),
    }
]

AUTHENTICITY_AUDIT_SCHEMA = {
    "required_fields": {
        "source_provenance": {"type": "string", "non_empty": True},
        "workflow_proximity_pass": {"type": "bool"},
        "anti_fake_workflow_pass": {"type": "bool"},
        "context_naturalness_risk": {"type": "enum", "allowed_values": list(CONTEXT_NATURALNESS_RISK_VALUES)},
        "goal_level_acceptance_is_realistic": {"type": "bool"},
        "authenticity_audit_pass": {"type": "bool"},
    },
    "interpretation_rules": [
        "authenticity_audit_pass is allowed only when workflow_proximity_pass, anti_fake_workflow_pass, and goal_level_acceptance_is_realistic are all true.",
        "context_naturalness_risk = high forces authenticity_audit_pass = false.",
        "context_naturalness_risk = medium is advisory and does not force rejection by itself.",
    ],
}

BARRIER_SAMPLING_AUDIT_SCHEMA = {
    "required_fields": {
        "barrier_sampling_intent_present": {"type": "bool"},
        "target_barrier_family": {"type": "string", "allow_empty": True},
        "barrier_sampling_rationale": {"type": "string", "allow_empty": True},
        "selection_priority_reason": {"type": "string", "allow_empty": True},
        "task_definition_was_changed_for_barrier_targeting": {"type": "bool"},
        "barrier_sampling_audit_pass": {"type": "bool"},
    },
    "interpretation_rules": [
        "Barrier-aware sampling may change selection priority but may not change task definition.",
        "task_definition_was_changed_for_barrier_targeting = true forces barrier_sampling_audit_pass = false.",
        "target_barrier_family must be one of the priority barriers when barrier_sampling_intent_present is true.",
    ],
}

CANDIDATE_REJECTION_RULES = [
    {"rule_id": "reject_missing_source_provenance", "description": "source provenance missing"},
    {"rule_id": "reject_workflow_proximity_fail", "description": "workflow proximity audit failed"},
    {"rule_id": "reject_anti_fake_workflow_fail", "description": "anti-fake-workflow audit failed"},
    {"rule_id": "reject_unrealistic_goal_acceptance", "description": "goal-level acceptance is not realistic"},
    {"rule_id": "reject_high_context_naturalness_risk", "description": "context_naturalness_risk = high"},
    {
        "rule_id": "reject_barrier_targeting_changed_task_definition",
        "description": "task definition was changed for barrier targeting",
    },
]

WORKFLOW_AUTHENTICITY_GUARD_DEFINITION = {
    "guard_name": "workflow_authenticity_guard_definition",
    "bound_skill": "Authenticity-Constrained Candidate Pool Governance Pattern",
    "selection_bias_allowed": True,
    "task_fabrication_allowed": False,
    "working_minimum_per_priority_barrier": WORKING_MINIMUM_PER_PRIORITY_BARRIER,
    "guardrail_statement": "Barrier-aware expansion may target underrepresented workflow barriers only through audited selection from real candidates.",
}


def _goal_specific_check_mode(task_row: dict) -> str:
    checks = task_row.get("workflow_acceptance_checks") if isinstance(task_row.get("workflow_acceptance_checks"), list) else []
    check_types = {str(check.get("type") or "") for check in checks if isinstance(check, dict)}
    if "expected_goal_artifact_present" in check_types:
        return "artifact_only"
    if "named_result_invariant_pass" in check_types:
        return "invariant_only"
    return "check_simulate_only"


def build_baseline_candidate_rows(
    *,
    v080_closeout_path: str = str(DEFAULT_V080_CLOSEOUT_PATH),
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
) -> list[dict]:
    v080 = load_json(v080_closeout_path)
    v081 = load_json(v081_closeout_path)
    substrate = v080.get("workflow_proximal_substrate") if isinstance(v080.get("workflow_proximal_substrate"), dict) else {}
    characterization = (
        v081.get("workflow_profile_characterization")
        if isinstance(v081.get("workflow_profile_characterization"), dict)
        else {}
    )

    task_rows = substrate.get("task_rows") if isinstance(substrate.get("task_rows"), list) else []
    case_rows = (
        characterization.get("case_characterization_table")
        if isinstance(characterization.get("case_characterization_table"), list)
        else []
    )
    case_by_task_id = {str(row.get("task_id")): row for row in case_rows if isinstance(row, dict)}

    candidates: list[dict] = []
    for task_row in task_rows:
        if not isinstance(task_row, dict):
            continue
        task_id = str(task_row.get("task_id") or "")
        case_row = case_by_task_id.get(task_id, {})
        barrier_label = str(case_row.get("primary_barrier_label") or "")
        barrier_intent_present = barrier_label in PRIORITY_BARRIERS
        workflow_proximity_pass = bool(task_row.get("workflow_proximity_audit_pass"))
        anti_fake_workflow_pass = bool(task_row.get("contextually_plausible")) and bool(
            task_row.get("non_trivial_from_context_alone")
        )
        goal_level_acceptance_is_realistic = bool(task_row.get("goal_specific_check_present")) and bool(
            task_row.get("workflow_goal_present")
        )
        context_naturalness_risk = "low" if anti_fake_workflow_pass else "high"
        authenticity_audit_pass = (
            workflow_proximity_pass
            and anti_fake_workflow_pass
            and goal_level_acceptance_is_realistic
            and context_naturalness_risk != "high"
        )
        barrier_sampling_audit_pass = not bool(task_row.get("task_definition_was_changed_for_barrier_targeting"))
        candidates.append(
            {
                "task_id": task_id,
                "base_task_id": task_row.get("base_task_id"),
                "source_id": CANDIDATE_SOURCE_REGISTRY[0]["source_id"],
                "family_id": task_row.get("family_id"),
                "workflow_task_template_id": task_row.get("workflow_task_template_id"),
                "complexity_tier": task_row.get("complexity_tier"),
                "goal_specific_check_mode": _goal_specific_check_mode(task_row),
                "current_pilot_outcome": case_row.get("pilot_outcome"),
                "current_primary_barrier_label": barrier_label,
                "authenticity_audit": {
                    "source_provenance": CANDIDATE_SOURCE_REGISTRY[0]["source_id"],
                    "workflow_proximity_pass": workflow_proximity_pass,
                    "anti_fake_workflow_pass": anti_fake_workflow_pass,
                    "context_naturalness_risk": context_naturalness_risk,
                    "goal_level_acceptance_is_realistic": goal_level_acceptance_is_realistic,
                    "authenticity_audit_pass": authenticity_audit_pass,
                },
                "barrier_sampling_audit": {
                    "barrier_sampling_intent_present": barrier_intent_present,
                    "target_barrier_family": barrier_label if barrier_intent_present else "",
                    "barrier_sampling_rationale": (
                        "Current frozen substrate already exhibits this workflow barrier and can be prioritized without changing task definition."
                        if barrier_intent_present
                        else ""
                    ),
                    "selection_priority_reason": (
                        "thin_v0_8_x_barrier_slice_needs_more_real_depth" if barrier_intent_present else ""
                    ),
                    "task_definition_was_changed_for_barrier_targeting": False,
                    "barrier_sampling_audit_pass": barrier_sampling_audit_pass,
                },
            }
        )
    return candidates


def build_v090_governance_pack(
    *,
    v080_closeout_path: str = str(DEFAULT_V080_CLOSEOUT_PATH),
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    candidate_rows = build_baseline_candidate_rows(
        v080_closeout_path=v080_closeout_path,
        v081_closeout_path=v081_closeout_path,
    )
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_governance_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "bound_skill": "Authenticity-Constrained Candidate Pool Governance Pattern",
        "candidate_source_registry": CANDIDATE_SOURCE_REGISTRY,
        "authenticity_audit_schema": AUTHENTICITY_AUDIT_SCHEMA,
        "barrier_sampling_audit_schema": BARRIER_SAMPLING_AUDIT_SCHEMA,
        "candidate_rejection_rules": CANDIDATE_REJECTION_RULES,
        "workflow_authenticity_guard_definition": WORKFLOW_AUTHENTICITY_GUARD_DEFINITION,
        "priority_barriers": list(PRIORITY_BARRIERS),
        "baseline_candidate_rows": candidate_rows,
        "candidate_pool_total_count": len(candidate_rows),
        "working_minimum_per_priority_barrier": WORKING_MINIMUM_PER_PRIORITY_BARRIER,
    }
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "governance_pack.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.0 Governance Pack",
                "",
                f"- candidate_pool_total_count: `{len(candidate_rows)}`",
                f"- priority_barriers: `{', '.join(PRIORITY_BARRIERS)}`",
                f"- working_minimum_per_priority_barrier: `{WORKING_MINIMUM_PER_PRIORITY_BARRIER}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.0 governance pack artifact.")
    parser.add_argument("--v080-closeout", default=str(DEFAULT_V080_CLOSEOUT_PATH))
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v090_governance_pack(
        v080_closeout_path=str(args.v080_closeout),
        v081_closeout_path=str(args.v081_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "candidate_pool_total_count": payload.get("candidate_pool_total_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
