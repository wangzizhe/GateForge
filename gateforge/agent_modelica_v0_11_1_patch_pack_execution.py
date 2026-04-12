from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .agent_modelica_l2_plan_replan_engine_v1 import (
    audit_planner_prompt_surface,
    build_source_blind_multistep_planner_prompt,
)
from .agent_modelica_v0_11_0_governance_pack import DEFAULT_PATCH_CANDIDATES
from .agent_modelica_v0_11_1_common import (
    DEFAULT_PATCH_PACK_EXECUTION_OUT_DIR,
    DEFAULT_V110_GOVERNANCE_PACK_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


_LIVE_EXECUTOR_SOURCE = Path(__file__).resolve().parent / "agent_modelica_live_executor_v1.py"

_SAMPLE_STAGE_CONTEXT = {
    "current_stage": "stage_1",
    "stage_2_branch": "",
    "preferred_stage_2_branch": "",
    "current_fail_bucket": "compile_or_simulate_failure",
    "branch_mode": "same_branch",
    "trap_branch": False,
}


def _sample_prompt(*, workflow_goal: str, error_excerpt: str) -> tuple[str, dict]:
    prompt, _planner_contract = build_source_blind_multistep_planner_prompt(
        original_text="model Demo\n  parameter Real k = 1;\nend Demo;\n",
        failure_type="simulate_error",
        expected_stage="simulate",
        error_excerpt=error_excerpt,
        repair_actions=["inspect_error_output", "propose_minimal_patch"],
        model_name="Demo",
        workflow_goal=workflow_goal,
        current_round=1,
        stage_context=dict(_SAMPLE_STAGE_CONTEXT),
        llm_reason="product_gap_patch_pack_validation",
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
    return prompt, audit


def _load_live_executor_source() -> str:
    return _LIVE_EXECUTOR_SOURCE.read_text(encoding="utf-8")


def build_v111_patch_pack_execution(
    *,
    v110_governance_pack_path: str = str(DEFAULT_V110_GOVERNANCE_PACK_PATH),
    out_dir: str = str(DEFAULT_PATCH_PACK_EXECUTION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    governance = load_json(v110_governance_pack_path)
    governance_rows = (
        governance.get("patch_candidates")
        if isinstance(governance.get("patch_candidates"), dict)
        else {}
    )
    live_executor_source = _load_live_executor_source()

    long_error_excerpt = "\n".join(
        [
            "Error: Variable gain has invalid value.",
            "Error: Controller state did not converge after initialization.",
            "Error: Assertion triggered inside control loop validation chain.",
            "Error: Detailed diagnostic payload retained for the next adaptive step.",
        ]
    )
    workflow_prompt, workflow_audit = _sample_prompt(
        workflow_goal="Recover the controller workflow so the validation path regains the intended behavior.",
        error_excerpt=long_error_excerpt,
    )
    error_prompt, error_audit = _sample_prompt(
        workflow_goal="Recover the simulation chain with full error carry-over.",
        error_excerpt=long_error_excerpt,
    )

    workflow_goal_row = copy.deepcopy(
        governance_rows.get("workflow_goal_reanchoring_patch_candidate")
        or DEFAULT_PATCH_CANDIDATES["workflow_goal_reanchoring_patch_candidate"]
    )
    workflow_goal_ok = (
        "- workflow_goal:" in workflow_prompt
        and bool(workflow_audit.get("workflow_goal_reanchoring_observed"))
        and 'parser.add_argument("--workflow-goal"' in live_executor_source
        and "workflow_goal=str(args.workflow_goal or \"\")" in live_executor_source
    )
    workflow_goal_row.update(
        {
            "execution_status": "implemented" if workflow_goal_ok else "partial",
            "implementation_mode": "runtime_patch",
            "evidence_field_name": "workflow_goal_reanchoring_observed",
            "why_this_row_is_or_is_not_complete": (
                "The planner prompt now carries workflow_goal explicitly and the live executor wires the field into the planning path."
                if workflow_goal_ok
                else "The workflow_goal field is not yet wired end-to-end through the planning surface."
            ),
        }
    )

    dynamic_audit_row = copy.deepcopy(
        governance_rows.get("system_prompt_dynamic_field_audit_patch_candidate")
        or DEFAULT_PATCH_CANDIDATES["system_prompt_dynamic_field_audit_patch_candidate"]
    )
    dynamic_result = workflow_audit.get("dynamic_system_prompt_field_audit_result") or {}
    dynamic_ok = (
        bool(dynamic_result.get("static_prefix_stable"))
        and not bool(dynamic_result.get("dynamic_timestamp_found"))
        and not bool(dynamic_result.get("dynamic_task_id_found"))
        and not bool(dynamic_result.get("absolute_path_found"))
        and "dynamic_system_prompt_field_audit_result" in live_executor_source
    )
    dynamic_audit_row.update(
        {
            "execution_status": "already_satisfied_by_audit" if dynamic_ok else "partial",
            "implementation_mode": "mixed_patch_and_audit",
            "evidence_field_name": "dynamic_system_prompt_field_audit_result",
            "why_this_row_is_or_is_not_complete": (
                "The planner prompt prefix audits as static-prefix-stable and the live executor now emits the audit result as side evidence."
                if dynamic_ok
                else "The dynamic-field audit is not yet explicit enough to count as governed side evidence."
            ),
        }
    )

    full_error_row = copy.deepcopy(
        governance_rows.get("full_omc_error_propagation_audit_patch_candidate")
        or DEFAULT_PATCH_CANDIDATES["full_omc_error_propagation_audit_patch_candidate"]
    )
    error_ok = (
        bool(error_audit.get("full_omc_error_propagation_observed"))
        and long_error_excerpt in error_prompt
        and 'error_excerpt=str(output or "")' in live_executor_source
        and '"full_omc_error_output":' in live_executor_source
        and 'str(output or "")' in live_executor_source
        and "full_omc_error_propagation_observed" in live_executor_source
    )
    full_error_row.update(
        {
            "execution_status": "implemented" if error_ok else "partial",
            "implementation_mode": "runtime_patch",
            "evidence_field_name": "full_omc_error_propagation_observed",
            "why_this_row_is_or_is_not_complete": (
                "The planner prompt now retains the full actionable OMC error excerpt and the live executor keeps the same full output in runtime artifacts."
                if error_ok
                else "Full actionable OMC error content is still truncated or not preserved explicitly enough."
            ),
        }
    )

    patch_rows = [
        workflow_goal_row,
        dynamic_audit_row,
        full_error_row,
    ]
    implemented_row_count = sum(1 for row in patch_rows if row["execution_status"] == "implemented")
    audit_only_row_count = sum(1 for row in patch_rows if row["execution_status"] == "already_satisfied_by_audit")
    partial_row_count = sum(1 for row in patch_rows if row["execution_status"] == "partial")
    invalid_row_count = sum(1 for row in patch_rows if row["execution_status"] == "invalid")

    if invalid_row_count:
        status = "invalid"
    elif partial_row_count:
        status = "partial"
    else:
        status = "ready"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_patch_pack_execution",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status == "ready" else ("PARTIAL" if status == "partial" else "FAIL"),
        "patch_pack_execution_status": status,
        "patch_rows": patch_rows,
        "implemented_row_count": implemented_row_count,
        "audit_only_row_count": audit_only_row_count,
        "partial_row_count": partial_row_count,
        "invalid_row_count": invalid_row_count,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.1 Patch Pack Execution",
                "",
                f"- patch_pack_execution_status: `{status}`",
                f"- implemented_row_count: `{implemented_row_count}`",
                f"- audit_only_row_count: `{audit_only_row_count}`",
                f"- partial_row_count: `{partial_row_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.1 patch-pack execution artifact.")
    parser.add_argument("--v110-governance-pack", default=str(DEFAULT_V110_GOVERNANCE_PACK_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PATCH_PACK_EXECUTION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v111_patch_pack_execution(
        v110_governance_pack_path=str(args.v110_governance_pack),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "patch_pack_execution_status": payload.get("patch_pack_execution_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
