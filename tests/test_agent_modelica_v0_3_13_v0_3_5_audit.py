from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_13_v0_3_5_audit import (
    build_audit_row,
    classify_masking_pattern,
    classify_success_pattern,
)


class AgentModelicaV0313V035AuditTests(unittest.TestCase):
    def test_classify_masking_pattern_detects_surface_masks_residual(self) -> None:
        result = {
            "attempts": [
                {"diagnostic_ir": {"stage_subtype": "stage_1_parse_syntax", "error_type": "model_check_error"}},
                {"diagnostic_ir": {"stage_subtype": "stage_4_initialization_singularity", "error_type": "simulate_error"}},
            ]
        }

        masking = classify_masking_pattern(result)

        self.assertEqual(masking, "surface_masks_residual")

    def test_classify_success_pattern_detects_rule_then_llm_multiround_success(self) -> None:
        result = {
            "executor_status": "PASS",
            "resolution_path": "rule_then_llm",
            "rounds_used": 3,
        }

        pattern = classify_success_pattern(result)

        self.assertEqual(pattern, "rule_then_llm_multiround_success")

    def test_build_audit_row_carries_preview_signal(self) -> None:
        candidate = {"task_id": "demo", "hidden_base_operator": "init_value_collapse"}
        result = {
            "task_id": "demo",
            "executor_status": "PASS",
            "resolution_path": "rule_then_llm",
            "rounds_used": 3,
            "llm_plan_candidate_parameters": ["m"],
            "attempts": [
                {"diagnostic_ir": {"stage_subtype": "stage_5_runtime_numerical_instability", "error_type": "numerical_instability"}},
                {"diagnostic_ir": {"stage_subtype": "stage_5_runtime_numerical_instability", "error_type": "numerical_instability"}},
            ],
        }
        preview = {
            "preview_admission": True,
            "surface_rule_id": "rule_simulate_error_injection_repair",
            "surface_rule_reason": "removed_gf_simulate_injection",
            "residual_signal_cluster_id": "runtime_parameter_recovery",
        }

        row = build_audit_row(candidate_row=candidate, result_row=result, preview_row=preview)

        self.assertTrue(row["preview_admission"])
        self.assertEqual(row["hidden_base_operator"], "init_value_collapse")
        self.assertEqual(row["residual_signal_cluster_id"], "runtime_parameter_recovery")


if __name__ == "__main__":
    unittest.main()
