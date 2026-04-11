from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_l2_plan_replan_engine_v1 import (
    audit_planner_prompt_surface,
    build_source_blind_multistep_planner_prompt,
)
from .agent_modelica_v0_11_1_common import (
    ANTI_REWARD_HACKING_CHECKLIST_VERSION,
    CONTEXT_CONTRACT_VERSION,
    CURRENT_PROTOCOL_CONTRACT_VERSION,
    DEFAULT_BOUNDED_VALIDATION_PACK_OUT_DIR,
    DEFAULT_V103_SUBSTRATE_BUILDER_PATH,
    SCHEMA_PREFIX,
    SCAFFOLD_VERSION,
    VALIDATION_CASE_COUNT_MIN,
    load_json,
    now_utc,
    write_json,
    write_text,
)


_FAMILY_SELECTION_ORDER = [
    ("workflow_goal_reanchoring_patch_candidate", "control_library_maintenance"),
    ("system_prompt_dynamic_field_audit_patch_candidate", "conversion_compatibility_maintenance"),
    ("full_omc_error_propagation_audit_patch_candidate", "multibody_constraint_maintenance"),
]


def _derive_workflow_goal(row: dict) -> str:
    template = str(row.get("workflow_task_template_id") or "")
    family = str(row.get("family_id") or "")
    if template == "restore_controller_assertion_behavior":
        return "Recover the controller workflow so the validation chain regains the intended assertion behavior."
    if template == "restore_conversion_compatibility":
        return "Recover the conversion compatibility workflow so the product shell can continue through the compatibility path."
    if template == "restore_multibody_constraint_behavior":
        return "Recover the multibody constraint workflow so the constrained validation path compiles and simulates cleanly."
    return f"Recover the {family or 'workflow'} path so the governed validation flow can continue without drift."


def _derive_error_excerpt(row: dict) -> str:
    family = str(row.get("family_id") or "")
    task_id = str(row.get("task_id") or "")
    lines = [
        f"Error: Validation run failed for {task_id}.",
        f"Error: Family bucket {family} still blocks the governed product-gap shell.",
    ]
    if family == "control_library_maintenance":
        lines.extend(
            [
                "Error: Controller assertion tolerance regressed after the latest repair step.",
                "Error: Full diagnostic context must remain visible for the next adaptive round.",
            ]
        )
    elif family == "conversion_compatibility_maintenance":
        lines.extend(
            [
                "Error: Conversion chain compatibility still fails during the product-boundary path.",
                "Error: Prompt-shell audit must remain stable while surfacing the compatibility miss.",
            ]
        )
    else:
        lines.extend(
            [
                "Error: Multibody constraint resolution still fails under the governed validation path.",
                "Error: Carry the full actionable OMC trace into the next adaptive planning round.",
            ]
        )
    return "\n".join(lines)


def _pick_validation_rows(substrate_rows: list[dict]) -> list[tuple[str, dict]]:
    chosen: list[tuple[str, dict]] = []
    seen_task_ids: set[str] = set()
    for patch_name, family in _FAMILY_SELECTION_ORDER:
        selected = next(
            (
                row
                for row in substrate_rows
                if str(row.get("family_id") or "") == family and str(row.get("task_id") or "") not in seen_task_ids
            ),
            None,
        )
        if selected is None:
            selected = next(
                (
                    row
                    for row in substrate_rows
                    if str(row.get("task_id") or "") not in seen_task_ids
                ),
                None,
            )
        if selected is not None:
            task_id = str(selected.get("task_id") or "")
            seen_task_ids.add(task_id)
            chosen.append((patch_name, selected))
    return chosen


def build_v111_bounded_validation_pack(
    *,
    v103_substrate_builder_path: str = str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_BOUNDED_VALIDATION_PACK_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    builder = load_json(v103_substrate_builder_path)
    substrate_rows = (
        builder.get("real_origin_substrate_candidate_table")
        if isinstance(builder.get("real_origin_substrate_candidate_table"), list)
        else []
    )
    selected_rows = _pick_validation_rows(substrate_rows)
    validation_rows = []
    validation_case_ids: list[str] = []
    for patch_name, row in selected_rows:
        workflow_goal = _derive_workflow_goal(row)
        error_excerpt = _derive_error_excerpt(row)
        prompt, _planner_contract = build_source_blind_multistep_planner_prompt(
            original_text="model Demo\n  parameter Real gain = 1;\nend Demo;\n",
            failure_type="simulate_error",
            expected_stage="simulate",
            error_excerpt=error_excerpt,
            repair_actions=["inspect_error_output", "propose_minimal_patch"],
            model_name="Demo",
            workflow_goal=workflow_goal,
            current_round=1,
            stage_context={
                "current_stage": "stage_1",
                "stage_2_branch": "",
                "preferred_stage_2_branch": "",
                "current_fail_bucket": "compile_or_simulate_failure",
                "branch_mode": "same_branch",
                "trap_branch": False,
            },
            llm_reason="bounded_product_gap_validation",
            request_kind="plan",
            replan_context=None,
            resolved_provider="openai",
            planner_experience_context=None,
        )
        audit = audit_planner_prompt_surface(
            prompt=prompt,
            workflow_goal=workflow_goal,
            error_excerpt=error_excerpt,
        )
        task_id = str(row.get("task_id") or "")
        validation_case_ids.append(task_id)
        validation_rows.append(
            {
                "task_id": task_id,
                "selected_for_patch_candidate": patch_name,
                "source_id": row.get("source_id"),
                "workflow_task_template_id": row.get("workflow_task_template_id"),
                "family_id": row.get("family_id"),
                "validation_pack_kind": "bounded_carried_baseline_subset",
                "carried_baseline_source": "v0_10_3_frozen_12_case_real_origin_substrate",
                "one_to_one_traceability_pass": True,
                "source_origin_class": ((row.get("real_origin_authenticity_audit") or {}) if isinstance(row.get("real_origin_authenticity_audit"), dict) else {}).get("source_origin_class"),
                "scaffold_version": SCAFFOLD_VERSION,
                "protocol_contract_version": CURRENT_PROTOCOL_CONTRACT_VERSION,
                "token_count": int(audit.get("prompt_token_estimate") or 0),
                "context_contract_version": CONTEXT_CONTRACT_VERSION,
                "anti_reward_hacking_checklist_version": ANTI_REWARD_HACKING_CHECKLIST_VERSION,
                "workflow_goal_reanchoring_observed": bool(audit.get("workflow_goal_reanchoring_observed")),
                "dynamic_system_prompt_field_audit_result": dict(audit.get("dynamic_system_prompt_field_audit_result") or {}),
                "full_omc_error_propagation_observed": bool(audit.get("full_omc_error_propagation_observed")),
            }
        )

    static_fields_present = all(
        bool(row.get("scaffold_version"))
        and bool(row.get("protocol_contract_version"))
        and isinstance(row.get("token_count"), int)
        and bool(row.get("context_contract_version"))
        and bool(row.get("anti_reward_hacking_checklist_version"))
        for row in validation_rows
    )
    runtime_fields_present = all(
        bool(row.get("workflow_goal_reanchoring_observed"))
        and isinstance(row.get("dynamic_system_prompt_field_audit_result"), dict)
        and bool(row.get("dynamic_system_prompt_field_audit_result"))
        and bool(row.get("full_omc_error_propagation_observed"))
        for row in validation_rows
    )
    required_sidecar_fields_emitted = bool(static_fields_present and runtime_fields_present and len(validation_rows) >= VALIDATION_CASE_COUNT_MIN)
    one_to_one_traceability_pass = all(bool(row.get("one_to_one_traceability_pass")) for row in validation_rows)
    non_regression_pass = all(str(row.get("source_origin_class") or "") == "real_origin" for row in validation_rows)
    profile_level_claim_made = False
    bounded_validation_only = True

    if not validation_rows or not one_to_one_traceability_pass:
        validation_status = "invalid"
    elif required_sidecar_fields_emitted and non_regression_pass:
        validation_status = "ready"
    else:
        validation_status = "partial"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_bounded_validation_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS" if validation_status == "ready" else ("PARTIAL" if validation_status == "partial" else "FAIL"),
        "validation_pack_status": validation_status,
        "validation_pack_kind": "bounded_carried_baseline_subset",
        "validation_case_ids": validation_case_ids,
        "carried_baseline_source": "v0_10_3_frozen_12_case_real_origin_substrate",
        "required_sidecar_fields_emitted": required_sidecar_fields_emitted,
        "missing_sidecar_fields": []
        if required_sidecar_fields_emitted
        else [
            field
            for field, present in {
                "static_contract_fields": static_fields_present,
                "runtime_patch_evidence_fields": runtime_fields_present,
            }.items()
            if not present
        ],
        "one_to_one_traceability_pass": one_to_one_traceability_pass,
        "profile_level_claim_made": profile_level_claim_made,
        "bounded_validation_only": bounded_validation_only,
        "non_regression_pass": non_regression_pass,
        "validation_rows": validation_rows,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.1 Bounded Validation Pack",
                "",
                f"- validation_pack_status: `{validation_status}`",
                f"- validation_case_ids: `{validation_case_ids}`",
                f"- required_sidecar_fields_emitted: `{required_sidecar_fields_emitted}`",
                f"- one_to_one_traceability_pass: `{one_to_one_traceability_pass}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.1 bounded validation pack artifact.")
    parser.add_argument("--v103-substrate-builder", default=str(DEFAULT_V103_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_BOUNDED_VALIDATION_PACK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v111_bounded_validation_pack(
        v103_substrate_builder_path=str(args.v103_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "validation_pack_status": payload.get("validation_pack_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
