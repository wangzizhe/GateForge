from __future__ import annotations

import unittest

from gateforge.agent_modelica_rule_engine_v1 import (
    RuleContext,
    RuleTier,
    apply_generic_parse_error_repair,
    apply_gf_injected_symbol_cleanup_repair,
    apply_parse_error_pre_repair,
    build_default_rule_registry,
)


class TestAgentModelicaRuleEngineV1(unittest.TestCase):
    def test_default_registry_rule_order_and_metadata(self) -> None:
        registry = build_default_rule_registry()
        self.assertEqual(
            [rule.attempt_field for rule in registry.rules],
            [
                "pre_repair",
                "gf_injected_symbol_cleanup_repair",
                "initialization_marker_repair",
                "wave2_marker_repair",
                "wave2_1_marker_repair",
                "wave2_2_marker_repair",
                "simulate_error_injection_repair",
                "multi_round_layered_repair",
            ],
        )
        self.assertEqual(registry.rules[0].rule_tier, RuleTier.DOMAIN_GENERAL_RULE)
        self.assertTrue(registry.rules[0].replay_eligible)
        self.assertEqual(registry.rules[1].rule_tier, RuleTier.MUTATION_CONTRACT_RULE)
        self.assertFalse(registry.rules[1].replay_eligible)
        self.assertEqual(registry.rules[-1].rule_tier, RuleTier.DOMAIN_GENERAL_RULE)
        self.assertTrue(registry.rules[-1].replay_eligible)

    def test_registry_stops_after_first_applied_rule(self) -> None:
        registry = build_default_rule_registry()
        ctx = RuleContext(
            current_text=(
                "model A\n"
                "  Real x;\n"
                "initial equation\n"
                "  0 = 1; // gateforge_initialization_infeasible\n"
                "equation\n"
                "  der(x) = 1.0; // gateforge_event_logic_error\n"
                "end A;\n"
            ),
            declared_failure_type="initialization_infeasible",
            output="",
            current_round=1,
            failure_bucket_before="initialization_infeasible",
        )

        results = registry.try_repairs(ctx)

        self.assertEqual(
            [result.attempt_field for result in results],
            ["pre_repair", "gf_injected_symbol_cleanup_repair", "initialization_marker_repair"],
        )
        self.assertFalse(results[0].applied)
        self.assertFalse(results[1].applied)
        self.assertTrue(results[2].applied)
        self.assertNotIn("gateforge_initialization_infeasible", results[2].new_text)
        self.assertIn("gateforge_event_logic_error", results[2].new_text)

    def test_applied_rule_audit_uses_canonical_fields(self) -> None:
        registry = build_default_rule_registry()
        ctx = RuleContext(
            current_text=(
                "model A\n"
                "  Real x;\n"
                "initial equation\n"
                "  0 = 1; // gateforge_initialization_infeasible\n"
                "equation\n"
                "  x = 1;\n"
                "end A;\n"
            ),
            declared_failure_type="initialization_infeasible",
            current_round=1,
            failure_bucket_before="initialization_infeasible",
        )

        results = registry.try_repairs(ctx)
        applied = results[-1]

        self.assertTrue(applied.applied)
        self.assertEqual(applied.rule_id, "rule_initialization_marker_repair")
        self.assertEqual(applied.action_key, "repair|initialization_marker_repair|rule_engine_v1")
        self.assertEqual(applied.attempt_field, "initialization_marker_repair")
        self.assertEqual(applied.rule_tier, RuleTier.MUTATION_CONTRACT_RULE)
        self.assertFalse(applied.replay_eligible)
        self.assertEqual(applied.failure_bucket_before, "initialization_infeasible")
        self.assertEqual(applied.failure_bucket_after, "retry_pending")
        self.assertEqual(applied.audit_dict.get("failure_bucket_before"), "initialization_infeasible")
        self.assertEqual(applied.audit_dict.get("failure_bucket_after"), "retry_pending")
        self.assertEqual(applied.audit_dict.get("rounds_consumed"), 1)

    def test_noop_rule_audit_keeps_bucket_and_rounds_consumed_zero(self) -> None:
        registry = build_default_rule_registry()
        ctx = RuleContext(
            current_text="model A\n  Real x;\nequation\n  x = 1;\nend A;\n",
            declared_failure_type="model_check_error",
            output="ordinary error without gateforge markers",
            current_round=1,
            failure_bucket_before="model_check_error",
        )

        result = registry.rules[0].apply(ctx)

        self.assertFalse(result.applied)
        self.assertEqual(result.failure_bucket_before, "model_check_error")
        self.assertEqual(result.failure_bucket_after, "model_check_error")
        self.assertEqual(result.audit_dict.get("rounds_consumed"), 0)
        self.assertEqual(result.audit_dict.get("attempt_field"), "pre_repair")

    def test_generic_parse_repair_does_not_consume_gateforge_block_fallback(self) -> None:
        model_text = (
            "model Demo\n"
            "  Real x;\n"
            "  Real __gf_state_17(start=0.0);\n"
            "  // GateForge mutation: parser poison\n"
            "equation\n"
            "  x = 1.0;\n"
            "end Demo;\n"
        )
        patched, audit = apply_generic_parse_error_repair(
            model_text,
            "Error: No viable alternative near token parameter",
            "script_parse_error",
        )
        self.assertFalse(audit["applied"])
        self.assertEqual(audit["reason"], "state_token_not_detected")
        self.assertEqual(patched, model_text)

    def test_gf_cleanup_repair_removes_gateforge_symbol_block(self) -> None:
        model_text = (
            "model Demo\n"
            "  Real x;\n"
            "  Real __gf_state_17(start=0.0);\n"
            "  // GateForge mutation: parser poison\n"
            "equation\n"
            "  x = 1.0;\n"
            "end Demo;\n"
        )
        patched, audit = apply_gf_injected_symbol_cleanup_repair(
            model_text,
            "Error: No viable alternative near token parameter",
            "script_parse_error",
        )
        self.assertTrue(audit["applied"])
        self.assertEqual(audit["reason"], "removed_gateforge_injected_symbol_block")
        self.assertNotIn("__gf_state_17", patched)

    def test_legacy_parse_wrapper_preserves_fallback_behavior(self) -> None:
        model_text = (
            "model Demo\n"
            "  Real x;\n"
            "  Real __gf_state_17(start=0.0);\n"
            "  // GateForge mutation: parser poison\n"
            "equation\n"
            "  x = 1.0;\n"
            "end Demo;\n"
        )
        patched, audit = apply_parse_error_pre_repair(
            model_text,
            "Error: No viable alternative near token parameter",
            "script_parse_error",
        )
        self.assertTrue(audit["applied"])
        self.assertEqual(audit["reason"], "removed_gateforge_injected_symbol_block")
        self.assertNotIn("__gf_state_17", patched)


if __name__ == "__main__":
    unittest.main()
