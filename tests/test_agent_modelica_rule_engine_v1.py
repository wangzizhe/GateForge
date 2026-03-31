from __future__ import annotations

import unittest
from dataclasses import dataclass

from gateforge.agent_modelica_rule_engine_v1 import (
    BaseRepairRule,
    RepairRuleRegistry,
    RuleContext,
    RuleResult,
    RuleTier,
    apply_generic_parse_error_repair,
    apply_gf_injected_symbol_cleanup_repair,
    apply_parse_error_pre_repair,
    build_failure_type_rule_priority_context,
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

    def test_resolve_rule_order_prioritizes_recommended_rule_ids(self) -> None:
        registry = build_default_rule_registry()
        ordered = registry.resolve_rule_order(
            {
                "recommended_rule_order": [
                    "rule_multi_round_layered_repair",
                    "rule_parse_error_pre_repair",
                ]
            }
        )
        self.assertEqual(
            [rule.rule_id for rule in ordered[:3]],
            [
                "rule_multi_round_layered_repair",
                "rule_parse_error_pre_repair",
                "rule_gf_injected_symbol_cleanup_repair",
            ],
        )

    def test_build_failure_type_rule_priority_context_promotes_multi_round_rule_after_round_one(self) -> None:
        payload = build_failure_type_rule_priority_context(
            failure_type="coupled_conflict_failure",
            current_round=2,
        )
        self.assertEqual(
            payload.get("recommended_rule_order"),
            ["rule_multi_round_layered_repair", "rule_parse_error_pre_repair"],
        )

    def test_build_failure_type_rule_priority_context_is_empty_in_round_one(self) -> None:
        payload = build_failure_type_rule_priority_context(
            failure_type="coupled_conflict_failure",
            current_round=1,
        )
        self.assertEqual(payload, {})

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
        self.assertIn("equation\n", patched)

    def test_gf_cleanup_repair_keeps_primary_equation_boundary(self) -> None:
        model_text = (
            "within Buildings.Fluid.Actuators.Dampers.Examples;\n"
            "model VAVBoxExponential\n"
            "  Real x;\n"
            "  // GateForge mutation: model check failure\n"
            "  __gf_undef_301100 = 1.0;\n"
            "equation\n"
            "  x = 1.0;\n"
            "end VAVBoxExponential;\n"
        )
        patched, audit = apply_gf_injected_symbol_cleanup_repair(
            model_text,
            "compile/syntax error",
            "model_check_error",
        )
        self.assertTrue(audit["applied"])
        self.assertIn(
            audit["reason"],
            {
                "removed_gateforge_injected_symbol_block",
                "removed_gateforge_injected_symbol_block_fallback",
            },
        )
        self.assertNotIn("__gf_undef_301100", patched)
        self.assertIn("equation\n  x = 1.0;\n", patched)

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

    def test_semantic_regression_parse_like_output_triggers_cleanup(self) -> None:
        model_text = (
            "model Demo\n"
            "  Real x;\n"
            "  Real __gf_state_301300(start=0.0);\n"
            "  // GateForge mutation: semantic regression\n"
            "equation\n"
            "  der(__gf_state_301300) = x;\n"
            "  x = 1.0;\n"
            "end Demo;\n"
        )
        patched, audit = apply_parse_error_pre_repair(
            model_text,
            "compile/syntax error",
            "semantic_regression",
        )
        self.assertTrue(audit["applied"])
        self.assertIn(audit["reason"], {
            "removed_lines_with_injected_state_tokens",
            "removed_gateforge_injected_symbol_block",
        })
        self.assertNotIn("__gf_state_301300", patched)
        self.assertIn("equation\n", patched)

    def test_try_repairs_uses_priority_context_to_change_first_applied_rule(self) -> None:
        @dataclass(frozen=True)
        class StubRule(BaseRepairRule):
            applied_text: str

            def apply(self, ctx: RuleContext) -> RuleResult:
                return RuleResult(
                    new_text=self.applied_text,
                    applied=True,
                    rule_id=self.rule_id,
                    action_key=self.action_key,
                    attempt_field=self.attempt_field,
                    rule_tier=self.rule_tier,
                    replay_eligible=self.replay_eligible,
                    audit_dict={
                        "applied": True,
                        "rule_id": self.rule_id,
                        "action_key": self.action_key,
                        "attempt_field": self.attempt_field,
                        "rule_tier": str(self.rule_tier.value),
                        "replay_eligible": bool(self.replay_eligible),
                        "failure_bucket_before": str(ctx.failure_bucket_before or ""),
                        "failure_bucket_after": "retry_pending",
                    },
                    failure_bucket_before=str(ctx.failure_bucket_before or ""),
                    failure_bucket_after="retry_pending",
                )

        registry = RepairRuleRegistry(
            rules=[
                StubRule(
                    rule_id="rule_a",
                    action_key="repair|a|test",
                    attempt_field="rule_a",
                    rule_tier=RuleTier.DOMAIN_GENERAL_RULE,
                    replay_eligible=True,
                    applied_text="A",
                ),
                StubRule(
                    rule_id="rule_b",
                    action_key="repair|b|test",
                    attempt_field="rule_b",
                    rule_tier=RuleTier.DOMAIN_GENERAL_RULE,
                    replay_eligible=True,
                    applied_text="B",
                ),
            ]
        )
        ctx = RuleContext(current_text="x", declared_failure_type="model_check_error", failure_bucket_before="model_check_error")

        default_results = registry.try_repairs(ctx)
        replay_results = registry.try_repairs(ctx, priority_context={"recommended_rule_order": ["rule_b", "rule_a"]})

        self.assertEqual(default_results[0].rule_id, "rule_a")
        self.assertEqual(replay_results[0].rule_id, "rule_b")
        self.assertEqual(replay_results[0].new_text, "B")


if __name__ == "__main__":
    unittest.main()
