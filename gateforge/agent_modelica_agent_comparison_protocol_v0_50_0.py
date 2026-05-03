from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_comparison_protocol_v0_50_0"

PILOT_CASE_IDS = (
    "sem_13_arrayed_connector_bus_refactor",
    "sem_32_four_segment_adapter_cross_node",
    "singleroot2_02_replaceable_probe_array",
)


def build_agent_comparison_protocol(*, version: str = "v0.50.0") -> dict[str, Any]:
    return {
        "version": version,
        "analysis_scope": "agent_comparison_protocol",
        "status": "PASS",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "comparison_scope": "pilot",
        "pilot_case_ids": list(PILOT_CASE_IDS),
        "shared_budget": {
            "max_steps": 10,
            "max_token_budget": 32000,
            "wall_clock_guidance": "record_elapsed_time_do_not_hard_fail_on_time_alone",
        },
        "arm_contracts": {
            "gateforge": {
                "allowed_capabilities": [
                    "declared_gateforge_tool_use_harness",
                    "check_model",
                    "simulate_model",
                    "submit_final",
                    "declared_diagnostic_tools_if_enabled",
                ],
                "prompt_visible_information": [
                    "visible_task_description",
                    "constraints",
                    "initial_model",
                    "raw_omc_feedback_from_tool_calls",
                ],
                "audit_only_information": [
                    "hidden_oracle",
                    "benchmark_pack_metadata",
                    "difficulty_bucket",
                    "known_hard_for",
                ],
            },
            "external_agent": {
                "allowed_capabilities": [
                    "native_agent_tools",
                    "repository_file_editing",
                    "shell_or_omc_invocation_if_available",
                ],
                "prompt_visible_information": [
                    "visible_task_description",
                    "constraints",
                    "initial_model",
                    "verification_command",
                    "submission_format",
                ],
                "audit_only_information": [
                    "hidden_oracle",
                    "difficulty_bucket",
                    "gateforge_internal_artifacts",
                ],
            },
        },
        "paired_design": {
            "same_case_pairing_required": True,
            "same_llm_when_possible": True,
            "primary_metric": "paired_case_pass_delta",
            "secondary_metrics": ["submit_rate", "omc_invocation_count", "failure_category"],
        },
        "discipline": {
            "wrapper_repair_forbidden": True,
            "hidden_routing_forbidden": True,
            "answer_leakage_forbidden": True,
            "external_agent_native_tools_allowed": True,
        },
    }


def write_agent_comparison_protocol_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_agent_comparison_protocol(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    summary = build_agent_comparison_protocol()
    write_agent_comparison_protocol_outputs(out_dir=out_dir, summary=summary)
    return summary
