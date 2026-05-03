from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKBENCH = REPO_ROOT / "artifacts" / "hard_positive_workbench_v0_60_0" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_positive_candidate_attempts_v0_60_1"

FAILED_SIMPLE_ATTEMPTS: tuple[dict[str, Any], ...] = (
    {
        "case_id": "sem_06_repl_array_flow",
        "attempt_id": "msl_probe_open_circuit",
        "attempt_family": "probe_flow_ownership",
        "verification_status": "FAIL",
        "observed_result": "check_or_simulate_not_verified",
    },
    {
        "case_id": "sem_13_arrayed_connector_bus_refactor",
        "attempt_id": "probe_flow_conservation",
        "attempt_family": "probe_flow_ownership",
        "verification_status": "FAIL",
        "observed_result": "check_or_simulate_not_verified",
    },
    {
        "case_id": "sem_26_three_segment_adapter_cross_node",
        "attempt_id": "adapter_high_i_zero",
        "attempt_family": "adapter_contract",
        "verification_status": "FAIL",
        "observed_result": "check_or_simulate_not_verified",
    },
    {
        "case_id": "sem_29_two_branch_probe_bus",
        "attempt_id": "probe_flow_conservation",
        "attempt_family": "probe_flow_ownership",
        "verification_status": "FAIL",
        "observed_result": "model_check_balanced_but_simulation_not_verified",
    },
    {
        "case_id": "sem_30_wide_probe_bus",
        "attempt_id": "probe_flow_conservation",
        "attempt_family": "probe_flow_ownership",
        "verification_status": "FAIL",
        "observed_result": "check_or_simulate_not_verified",
    },
    {
        "case_id": "sem_31_probe_bus_resistance_shift",
        "attempt_id": "probe_flow_conservation",
        "attempt_family": "probe_flow_ownership",
        "verification_status": "FAIL",
        "observed_result": "check_or_simulate_not_verified",
    },
    {
        "case_id": "sem_32_four_segment_adapter_cross_node",
        "attempt_id": "adapter_high_i_zero",
        "attempt_family": "adapter_contract",
        "verification_status": "FAIL",
        "observed_result": "check_or_simulate_not_verified",
    },
    {
        "case_id": "sem_34_ladder_adapter_cross_node",
        "attempt_id": "adapter_high_i_zero",
        "attempt_family": "adapter_contract",
        "verification_status": "FAIL",
        "observed_result": "check_or_simulate_not_verified",
    },
    {
        "case_id": "sem_35_adapter_resistance_shift",
        "attempt_id": "adapter_high_i_zero",
        "attempt_family": "adapter_contract",
        "verification_status": "FAIL",
        "observed_result": "check_or_simulate_not_verified",
    },
)


def build_hard_positive_candidate_attempts(
    *,
    workbench_summary: dict[str, Any],
    attempts: tuple[dict[str, Any], ...] = FAILED_SIMPLE_ATTEMPTS,
    version: str = "v0.60.1",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    case_ids = set(str(case_id) for case_id in workbench_summary.get("case_ids") or [])
    rows = [dict(attempt) for attempt in attempts if str(attempt.get("case_id") or "") in case_ids]
    verified_pass = [row for row in rows if row.get("verification_status") == "PASS"]
    failed = [row for row in rows if row.get("verification_status") != "PASS"]
    cases_with_attempts = sorted({str(row["case_id"]) for row in rows})
    cases_without_attempts = sorted(case_id for case_id in case_ids if case_id not in set(cases_with_attempts))
    return (
        {
            "version": version,
            "analysis_scope": "hard_positive_candidate_attempts",
            "status": "PASS" if rows else "REVIEW",
            "evidence_role": "debug",
            "conclusion_allowed": False,
            "artifact_complete": True,
            "readiness_status": "simple_candidate_attempts_recorded",
            "case_count": len(case_ids),
            "attempt_count": len(rows),
            "verified_pass_count": len(verified_pass),
            "failed_attempt_count": len(failed),
            "cases_with_attempts": cases_with_attempts,
            "cases_without_attempts": cases_without_attempts,
            "scope_contract": {
                "attempts_are_hidden_audit_only": True,
                "failed_attempts_do_not_enter_prompt": True,
                "wrapper_repair_allowed": False,
            },
            "decision": "do_not_repeat_simple_flow_or_adapter_patch_as_reference_solution",
            "next_actions": [
                "perform_deeper_manual_reference_repair_or_demote_to_frontier",
                "verify_any_new_reference_candidate_with_omc_before_promotion",
            ],
        },
        rows,
    )


def write_hard_positive_candidate_attempts_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "attempts.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_hard_positive_candidate_attempts(
    *,
    workbench_path: Path = DEFAULT_WORKBENCH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, rows = build_hard_positive_candidate_attempts(workbench_summary=load_json(workbench_path))
    write_hard_positive_candidate_attempts_outputs(out_dir=out_dir, summary=summary, rows=rows)
    return summary
