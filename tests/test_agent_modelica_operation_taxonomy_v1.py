"""Tests for operation taxonomy and policy modules.

Pure-function tests: no Docker, LLM, OMC, or filesystem dependencies.
"""
from __future__ import annotations

import unittest

from gateforge.agent_modelica_operation_taxonomy_v1 import (
    OP_CLASS_DESTRUCTIVE,
    OP_CLASS_MUTATING,
    OP_CLASS_READ_ONLY,
    OPERATION_REGISTRY,
    OperationSpec,
    all_operations,
    get_operation,
)
from gateforge.agent_modelica_operation_policy_v1 import (
    allows_concurrency,
    is_budget_tracked,
    is_planner_event,
    is_verifier_visible,
    operation_summary,
    requires_checkpoint,
    requires_safety_gate,
)


# ===========================================================================
# Taxonomy: OperationSpec structural invariants
# ===========================================================================


class TestOperationSpecInvariants(unittest.TestCase):
    def test_all_registry_entries_have_consistent_name(self) -> None:
        for key, spec in OPERATION_REGISTRY.items():
            self.assertEqual(key, spec.name, f"Registry key '{key}' != spec.name '{spec.name}'")

    def test_all_registry_entries_have_valid_op_class(self) -> None:
        valid = {OP_CLASS_READ_ONLY, OP_CLASS_MUTATING, OP_CLASS_DESTRUCTIVE}
        for spec in OPERATION_REGISTRY.values():
            self.assertIn(spec.op_class, valid, f"{spec.name} has unknown op_class '{spec.op_class}'")

    def test_destructive_implies_mutates_candidate_or_workspace(self) -> None:
        for spec in OPERATION_REGISTRY.values():
            if spec.op_class == OP_CLASS_DESTRUCTIVE:
                self.assertTrue(
                    spec.mutates_candidate or spec.mutates_workspace,
                    f"Destructive op '{spec.name}' should mutate candidate or workspace",
                )

    def test_read_only_does_not_mutate(self) -> None:
        for spec in OPERATION_REGISTRY.values():
            if spec.op_class == OP_CLASS_READ_ONLY:
                self.assertFalse(spec.mutates_candidate, f"{spec.name} is read_only but mutates_candidate=True")
                self.assertFalse(spec.mutates_workspace, f"{spec.name} is read_only but mutates_workspace=True")
                self.assertFalse(spec.requires_exclusive, f"{spec.name} is read_only but requires_exclusive=True")

    def test_spec_is_frozen(self) -> None:
        spec = get_operation("omc_check")
        with self.assertRaises((AttributeError, TypeError)):
            spec.op_class = "mutating"  # type: ignore[misc]


# ===========================================================================
# Taxonomy: individual operation facts
# ===========================================================================


class TestReadOnlyOperations(unittest.TestCase):
    def _assert_read_only(self, name: str) -> None:
        spec = get_operation(name)
        self.assertEqual(spec.op_class, OP_CLASS_READ_ONLY)
        self.assertFalse(spec.mutates_candidate)
        self.assertFalse(spec.mutates_workspace)
        self.assertFalse(spec.requires_exclusive)
        self.assertFalse(spec.consumes_budget)

    def test_omc_check(self) -> None:
        self._assert_read_only("omc_check")

    def test_omc_simulate(self) -> None:
        self._assert_read_only("omc_simulate")

    def test_replay_lookup(self) -> None:
        self._assert_read_only("replay_lookup")


class TestPlannerInvoke(unittest.TestCase):
    def test_is_mutating(self) -> None:
        spec = get_operation("planner_invoke")
        self.assertEqual(spec.op_class, OP_CLASS_MUTATING)

    def test_consumes_budget(self) -> None:
        spec = get_operation("planner_invoke")
        self.assertTrue(spec.consumes_budget)

    def test_does_not_mutate_files(self) -> None:
        spec = get_operation("planner_invoke")
        self.assertFalse(spec.mutates_candidate)
        self.assertFalse(spec.mutates_workspace)

    def test_not_exclusive(self) -> None:
        spec = get_operation("planner_invoke")
        self.assertFalse(spec.requires_exclusive)


class TestApplyRepair(unittest.TestCase):
    def test_is_mutating(self) -> None:
        spec = get_operation("apply_repair")
        self.assertEqual(spec.op_class, OP_CLASS_MUTATING)

    def test_mutates_candidate_and_workspace(self) -> None:
        spec = get_operation("apply_repair")
        self.assertTrue(spec.mutates_candidate)
        self.assertTrue(spec.mutates_workspace)

    def test_requires_exclusive(self) -> None:
        # apply_repair writes candidate file; must not run concurrently
        spec = get_operation("apply_repair")
        self.assertTrue(spec.requires_exclusive)

    def test_does_not_consume_budget(self) -> None:
        spec = get_operation("apply_repair")
        self.assertFalse(spec.consumes_budget)


class TestRestoreSource(unittest.TestCase):
    def test_is_destructive(self) -> None:
        spec = get_operation("restore_source")
        self.assertEqual(spec.op_class, OP_CLASS_DESTRUCTIVE)

    def test_mutates_both(self) -> None:
        spec = get_operation("restore_source")
        self.assertTrue(spec.mutates_candidate)
        self.assertTrue(spec.mutates_workspace)

    def test_requires_exclusive(self) -> None:
        spec = get_operation("restore_source")
        self.assertTrue(spec.requires_exclusive)


# ===========================================================================
# Taxonomy: registry API
# ===========================================================================


class TestRegistryAPI(unittest.TestCase):
    def test_get_operation_returns_correct_spec(self) -> None:
        spec = get_operation("omc_check")
        self.assertIsInstance(spec, OperationSpec)
        self.assertEqual(spec.name, "omc_check")

    def test_get_operation_raises_on_unknown(self) -> None:
        with self.assertRaises(KeyError):
            get_operation("nonexistent_operation")

    def test_all_operations_returns_list(self) -> None:
        ops = all_operations()
        self.assertIsInstance(ops, list)
        self.assertEqual(len(ops), len(OPERATION_REGISTRY))

    def test_all_operations_contains_known_names(self) -> None:
        names = {spec.name for spec in all_operations()}
        for expected in ("omc_check", "omc_simulate", "replay_lookup",
                         "planner_invoke", "apply_repair", "restore_source"):
            self.assertIn(expected, names)


# ===========================================================================
# Policy: requires_checkpoint
# ===========================================================================


class TestRequiresCheckpoint(unittest.TestCase):
    def test_read_only_ops_do_not_require_checkpoint(self) -> None:
        for name in ("omc_check", "omc_simulate", "replay_lookup"):
            self.assertFalse(requires_checkpoint(get_operation(name)), name)

    def test_apply_repair_requires_checkpoint(self) -> None:
        self.assertTrue(requires_checkpoint(get_operation("apply_repair")))

    def test_restore_source_requires_checkpoint(self) -> None:
        self.assertTrue(requires_checkpoint(get_operation("restore_source")))

    def test_planner_invoke_does_not_require_checkpoint(self) -> None:
        # planner_invoke does not mutate files
        self.assertFalse(requires_checkpoint(get_operation("planner_invoke")))


# ===========================================================================
# Policy: requires_safety_gate
# ===========================================================================


class TestRequiresSafetyGate(unittest.TestCase):
    def test_destructive_always_gated(self) -> None:
        spec = get_operation("restore_source")
        for profile in ("default", "rule_only", "planner_heavy", "evidence_verifier"):
            self.assertTrue(requires_safety_gate(spec, profile), f"profile={profile}")

    def test_read_only_never_gated_in_default(self) -> None:
        for name in ("omc_check", "omc_simulate", "replay_lookup"):
            self.assertFalse(requires_safety_gate(get_operation(name), "default"), name)

    def test_apply_repair_not_gated_in_default(self) -> None:
        self.assertFalse(requires_safety_gate(get_operation("apply_repair"), "default"))

    def test_apply_repair_gated_in_planner_heavy(self) -> None:
        self.assertTrue(requires_safety_gate(get_operation("apply_repair"), "planner_heavy"))

    def test_planner_invoke_not_gated_in_planner_heavy(self) -> None:
        # planner_invoke does not mutate candidate, so no gate even in planner_heavy
        self.assertFalse(requires_safety_gate(get_operation("planner_invoke"), "planner_heavy"))


# ===========================================================================
# Policy: allows_concurrency
# ===========================================================================


class TestAllowsConcurrency(unittest.TestCase):
    def test_read_only_ops_allow_concurrency(self) -> None:
        for name in ("omc_check", "omc_simulate", "replay_lookup"):
            self.assertTrue(allows_concurrency(get_operation(name)), name)

    def test_exclusive_ops_do_not_allow_concurrency(self) -> None:
        for name in ("apply_repair", "restore_source"):
            self.assertFalse(allows_concurrency(get_operation(name)), name)

    def test_planner_invoke_allows_concurrency(self) -> None:
        self.assertTrue(allows_concurrency(get_operation("planner_invoke")))


# ===========================================================================
# Policy: is_verifier_visible
# ===========================================================================


class TestIsVerifierVisible(unittest.TestCase):
    def test_read_only_ops_not_verifier_visible(self) -> None:
        for name in ("omc_check", "omc_simulate", "replay_lookup"):
            self.assertFalse(is_verifier_visible(get_operation(name)), name)

    def test_mutating_file_ops_are_verifier_visible(self) -> None:
        for name in ("apply_repair", "restore_source"):
            self.assertTrue(is_verifier_visible(get_operation(name)), name)

    def test_planner_invoke_not_verifier_visible(self) -> None:
        # planner_invoke does not change files; not part of repair audit trail
        self.assertFalse(is_verifier_visible(get_operation("planner_invoke")))


# ===========================================================================
# Policy: is_budget_tracked
# ===========================================================================


class TestIsBudgetTracked(unittest.TestCase):
    def test_planner_invoke_is_budget_tracked(self) -> None:
        self.assertTrue(is_budget_tracked(get_operation("planner_invoke")))

    def test_mutating_ops_are_budget_tracked(self) -> None:
        self.assertTrue(is_budget_tracked(get_operation("apply_repair")))

    def test_destructive_ops_are_budget_tracked(self) -> None:
        self.assertTrue(is_budget_tracked(get_operation("restore_source")))

    def test_read_only_ops_not_budget_tracked(self) -> None:
        for name in ("omc_check", "omc_simulate", "replay_lookup"):
            self.assertFalse(is_budget_tracked(get_operation(name)), name)


# ===========================================================================
# Policy: is_planner_event
# ===========================================================================


class TestIsPlannerEvent(unittest.TestCase):
    def test_planner_invoke_is_planner_event(self) -> None:
        self.assertTrue(is_planner_event(get_operation("planner_invoke")))

    def test_read_only_ops_are_not_planner_events(self) -> None:
        for name in ("omc_check", "omc_simulate", "replay_lookup"):
            self.assertFalse(is_planner_event(get_operation(name)), name)

    def test_apply_repair_is_not_planner_event(self) -> None:
        self.assertFalse(is_planner_event(get_operation("apply_repair")))

    def test_restore_source_is_not_planner_event(self) -> None:
        self.assertFalse(is_planner_event(get_operation("restore_source")))

    def test_planner_event_and_verifier_visible_are_disjoint_in_registry(self) -> None:
        # Currently no operation is both a planner event AND verifier-visible
        for spec in all_operations():
            if is_planner_event(spec):
                self.assertFalse(
                    is_verifier_visible(spec),
                    f"{spec.name} is both planner_event and verifier_visible — update this test if intentional",
                )


# ===========================================================================
# Policy: operation_summary
# ===========================================================================


class TestOperationSummary(unittest.TestCase):
    def test_summary_contains_required_keys(self) -> None:
        summary = operation_summary(get_operation("apply_repair"))
        for key in ("name", "op_class", "requires_checkpoint", "requires_safety_gate",
                    "allows_concurrency", "is_verifier_visible", "is_budget_tracked",
                    "is_planner_event"):
            self.assertIn(key, summary, f"Missing key: {key}")

    def test_summary_name_matches_spec(self) -> None:
        summary = operation_summary(get_operation("omc_check"))
        self.assertEqual(summary["name"], "omc_check")

    def test_summary_profile_affects_safety_gate(self) -> None:
        spec = get_operation("apply_repair")
        default_summary = operation_summary(spec, "default")
        planner_summary = operation_summary(spec, "planner_heavy")
        self.assertFalse(default_summary["requires_safety_gate"])
        self.assertTrue(planner_summary["requires_safety_gate"])

    def test_summary_is_planner_event_true_for_planner_invoke(self) -> None:
        summary = operation_summary(get_operation("planner_invoke"))
        self.assertTrue(summary["is_planner_event"])

    def test_summary_is_planner_event_false_for_apply_repair(self) -> None:
        summary = operation_summary(get_operation("apply_repair"))
        self.assertFalse(summary["is_planner_event"])


if __name__ == "__main__":
    unittest.main()
