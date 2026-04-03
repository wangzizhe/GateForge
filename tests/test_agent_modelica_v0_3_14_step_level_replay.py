from __future__ import annotations

import unittest

from gateforge.agent_modelica_experience_replay_v1 import build_rule_priority_context
from gateforge.agent_modelica_planner_experience_context_v1 import build_planner_experience_context


class AgentModelicaV0314StepLevelReplayTests(unittest.TestCase):
    def _experience_store(self) -> dict:
        return {
            "schema_version": "agent_modelica_v0_3_14_experience_store",
            "step_records": [
                {
                    "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                    "residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
                    "action_type": "simulate_error_injection_repair",
                    "action_key": "repair|simulate_error_injection_repair|rule_engine_v1",
                    "rule_id": "rule_simulate_error_injection_repair",
                    "rule_tier": "domain_general_rule",
                    "replay_eligible": True,
                    "step_outcome": "non_progress",
                },
                {
                    "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                    "residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
                    "action_type": "simulate_error_parameter_recovery",
                    "action_key": "",
                    "rule_id": "",
                    "rule_tier": "",
                    "replay_eligible": True,
                    "step_outcome": "advancing",
                },
                {
                    "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                    "residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
                    "action_type": "simulate_error_injection_repair",
                    "action_key": "repair|simulate_error_injection_repair|rule_engine_v1",
                    "rule_id": "rule_simulate_error_injection_repair",
                    "rule_tier": "domain_general_rule",
                    "replay_eligible": True,
                    "step_outcome": "dead_end",
                },
                {
                    "dominant_stage_subtype": "stage_1_parse_syntax",
                    "residual_signal_cluster": "stage_1_parse_syntax|parse_lexer_error",
                    "action_type": "gf_injected_symbol_cleanup_repair",
                    "action_key": "repair|gf_injected_symbol_cleanup_repair|rule_engine_v1",
                    "rule_id": "rule_gf_injected_symbol_cleanup_repair",
                    "rule_tier": "domain_general_rule",
                    "replay_eligible": True,
                    "step_outcome": "advancing",
                },
            ],
        }

    def test_exact_match_rule_priority_context_uses_stage_and_cluster(self) -> None:
        context = build_rule_priority_context(
            self._experience_store(),
            failure_type="simulate_error",
            dominant_stage_subtype="stage_5_runtime_numerical_instability",
            residual_signal_cluster="stage_5_runtime_numerical_instability|division_by_zero",
        )
        self.assertEqual(context.get("coverage", {}).get("signal_coverage_status"), "exact_step_match_available")
        self.assertEqual(context.get("coverage", {}).get("exact_match_step_count"), 3)
        ranked = context.get("ranked_rules") or []
        self.assertEqual((ranked[0] if ranked else {}).get("rule_id"), "rule_simulate_error_injection_repair")

    def test_exact_match_planner_context_emits_step_level_hint_text(self) -> None:
        context = build_planner_experience_context(
            self._experience_store(),
            failure_type="simulate_error",
            dominant_stage_subtype="stage_5_runtime_numerical_instability",
            residual_signal_cluster="stage_5_runtime_numerical_instability|division_by_zero",
            max_context_tokens=120,
        )
        self.assertTrue(bool(context.get("used")))
        prompt_context = str(context.get("prompt_context_text") or "")
        self.assertIn("Historical success on stage_5_runtime_numerical_instability", prompt_context)
        self.assertIn("simulate_error_parameter_recovery", prompt_context)


if __name__ == "__main__":
    unittest.main()
