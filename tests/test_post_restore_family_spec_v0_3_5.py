"""
Tests for agent_modelica_post_restore_family_spec_v0_3_5.

Covers:
- stage gate: disqualified stage subtypes, required stage subtypes, unknown
- source restore gate: dual_layer pass, behavioral_contract pass, covered type fail, new type pass
- marker gate: dual_layer pass, marker_only fail, explicit false pass, unknown provisional
- planner sensitivity gate: each signal path
- run_admission_gates: all-pass, partial fail
- build_lane_summary: empty, composition fail, below minimum, candidate ready, freeze ready
"""

import unittest

from gateforge.agent_modelica_post_restore_family_spec_v0_3_5 import (
    DISQUALIFIED_STAGE_SUBTYPES,
    MIN_CANDIDATE_READY_COUNT,
    MIN_FREEZE_READY_COUNT,
    build_lane_summary,
    check_marker_gate,
    check_planner_sensitivity_gate,
    check_source_restore_gate,
    check_stage_gate,
    run_admission_gates,
)


class TestStageGate(unittest.TestCase):
    def test_disqualified_stage_subtypes(self):
        for subtype in DISQUALIFIED_STAGE_SUBTYPES:
            passed, reason = check_stage_gate({"dominant_stage_subtype": subtype})
            self.assertFalse(passed, f"expected fail for {subtype}")
            self.assertIn("stage_disqualified", reason)

    def test_required_stage_4(self):
        passed, reason = check_stage_gate({"dominant_stage_subtype": "stage_4_initialization_singularity"})
        self.assertTrue(passed)
        self.assertIn("stage_ok", reason)

    def test_required_stage_5(self):
        passed, reason = check_stage_gate({"dominant_stage_subtype": "stage_5_runtime_numerical_instability"})
        self.assertTrue(passed)
        self.assertIn("stage_ok", reason)

    def test_unknown_stage_provisional_pass(self):
        passed, reason = check_stage_gate({"dominant_stage_subtype": "stage_99_unknown"})
        self.assertTrue(passed)
        self.assertIn("provisional", reason)

    def test_missing_stage_provisional_pass(self):
        passed, reason = check_stage_gate({})
        self.assertTrue(passed)
        self.assertIn("provisional", reason)

    def test_stage_subtype_fallback(self):
        passed, reason = check_stage_gate({"stage_subtype": "stage_4_initialization_singularity"})
        self.assertTrue(passed)
        self.assertIn("stage_ok", reason)


class TestSourceRestoreGate(unittest.TestCase):
    def test_dual_layer_passes(self):
        passed, reason = check_source_restore_gate({
            "dual_layer_mutation": True,
            "declared_failure_type": "coupled_conflict_failure",
        })
        self.assertTrue(passed)
        self.assertIn("dual_layer", reason)

    def test_behavioral_contract_passes(self):
        passed, reason = check_source_restore_gate({
            "behavioral_contract_mode": True,
            "declared_failure_type": "coupled_conflict_failure",
        })
        self.assertTrue(passed)
        self.assertIn("behavioral_contract", reason)

    def test_covered_type_fails_without_override(self):
        passed, reason = check_source_restore_gate({
            "declared_failure_type": "coupled_conflict_failure",
        })
        self.assertFalse(passed)
        self.assertIn("source_restore_bypass_risk", reason)

    def test_uncovered_type_passes(self):
        passed, reason = check_source_restore_gate({
            "declared_failure_type": "post_restore_init_residual",
        })
        self.assertTrue(passed)
        self.assertIn("not_in_dispatch", reason)

    def test_failure_type_field_alias(self):
        passed, reason = check_source_restore_gate({
            "failure_type": "cascading_structural_failure",
        })
        self.assertFalse(passed)
        self.assertIn("source_restore_bypass_risk", reason)


class TestMarkerGate(unittest.TestCase):
    def test_dual_layer_passes(self):
        passed, reason = check_marker_gate({"dual_layer_mutation": True})
        self.assertTrue(passed)
        self.assertIn("dual_layer", reason)

    def test_behavioral_contract_passes(self):
        passed, reason = check_marker_gate({"behavioral_contract_mode": True})
        self.assertTrue(passed)
        self.assertIn("behavioral_contract", reason)

    def test_marker_only_true_fails(self):
        passed, reason = check_marker_gate({"marker_only_repair": True})
        self.assertFalse(passed)
        self.assertIn("marker_only_repair_disqualifies", reason)

    def test_marker_only_false_passes(self):
        passed, reason = check_marker_gate({"marker_only_repair": False})
        self.assertTrue(passed)
        self.assertIn("explicitly_false", reason)

    def test_missing_marker_only_provisional(self):
        passed, reason = check_marker_gate({})
        self.assertTrue(passed)
        self.assertIn("provisional", reason)


class TestPlannerSensitivityGate(unittest.TestCase):
    def test_planner_invoked(self):
        passed, reason = check_planner_sensitivity_gate({"planner_invoked": True})
        self.assertTrue(passed)
        self.assertIn("planner_invoked", reason)

    def test_multi_round_with_llm(self):
        passed, reason = check_planner_sensitivity_gate({
            "rounds_used": 3,
            "llm_request_count": 2,
        })
        self.assertTrue(passed)
        self.assertIn("multi_round_with_llm", reason)

    def test_multi_round_no_llm_fails(self):
        passed, reason = check_planner_sensitivity_gate({
            "rounds_used": 3,
            "llm_request_count": 0,
        })
        self.assertFalse(passed)

    def test_resolution_path_llm_planner_assisted(self):
        passed, reason = check_planner_sensitivity_gate({
            "resolution_path": "llm_planner_assisted",
        })
        self.assertTrue(passed)
        self.assertIn("resolution_path", reason)

    def test_resolution_path_rule_then_llm(self):
        passed, reason = check_planner_sensitivity_gate({
            "resolution_path": "rule_then_llm",
        })
        self.assertTrue(passed)
        self.assertIn("resolution_path", reason)

    def test_deterministic_only_fails(self):
        passed, reason = check_planner_sensitivity_gate({
            "resolution_path": "deterministic_rule_only",
            "planner_invoked": False,
            "rounds_used": 2,
            "llm_request_count": 0,
        })
        self.assertFalse(passed)

    def test_no_signals_fails(self):
        passed, reason = check_planner_sensitivity_gate({})
        self.assertFalse(passed)

    def test_dual_layer_mutation_structural_bypass(self):
        passed, reason = check_planner_sensitivity_gate({"dual_layer_mutation": True})
        self.assertTrue(passed)
        self.assertIn("dual_layer_structural_guarantee", reason)

    def test_dual_layer_false_not_bypassed(self):
        passed, reason = check_planner_sensitivity_gate({"dual_layer_mutation": False})
        self.assertFalse(passed)

    def test_dual_layer_none_fields_bypass_applies(self):
        # planner_invoked=None means "not yet run" (pre-GateForge).
        # None is not empirical evidence; structural bypass still applies.
        passed, reason = check_planner_sensitivity_gate({
            "dual_layer_mutation": True,
            "planner_invoked": None,
            "rounds_used": None,
            "resolution_path": None,
        })
        self.assertTrue(passed)
        self.assertIn("dual_layer_structural_guarantee", reason)

    def test_dual_layer_explicit_false_bypasses_ignored(self):
        # planner_invoked=False is explicit empirical evidence (post-GateForge).
        # Structural bypass does NOT apply; falls through to empirical check which fails.
        passed, reason = check_planner_sensitivity_gate({
            "dual_layer_mutation": True,
            "planner_invoked": False,
            "resolution_path": "deterministic_rule_only",
            "rounds_used": 2,
            "llm_request_count": 0,
        })
        self.assertFalse(passed)


class TestRunAdmissionGates(unittest.TestCase):
    def _make_passing_candidate(self, task_id: str = "t1") -> dict:
        return {
            "task_id": task_id,
            "dominant_stage_subtype": "stage_4_initialization_singularity",
            "dual_layer_mutation": True,
            "marker_only_repair": False,
            "planner_invoked": True,
        }

    def test_all_gates_pass(self):
        result = run_admission_gates(self._make_passing_candidate())
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["reasons"]), 0)
        self.assertEqual(len(result["gates"]), 4)

    def test_stage_gate_fails(self):
        c = self._make_passing_candidate()
        c["dominant_stage_subtype"] = "stage_2_structural_balance_reference"
        result = run_admission_gates(c)
        self.assertFalse(result["passed"])
        self.assertTrue(any("stage_gate" in r for r in result["reasons"]))

    def test_source_restore_gate_fails(self):
        c = self._make_passing_candidate()
        c.pop("dual_layer_mutation")
        c["declared_failure_type"] = "coupled_conflict_failure"
        result = run_admission_gates(c)
        self.assertFalse(result["passed"])
        self.assertTrue(any("source_restore_gate" in r for r in result["reasons"]))

    def test_planner_gate_fails(self):
        c = self._make_passing_candidate()
        c["planner_invoked"] = False
        c["resolution_path"] = "deterministic_rule_only"
        c["rounds_used"] = 2
        c["llm_request_count"] = 0
        result = run_admission_gates(c)
        self.assertFalse(result["passed"])
        self.assertTrue(any("planner_sensitivity_gate" in r for r in result["reasons"]))

    def test_task_id_preserved(self):
        result = run_admission_gates(self._make_passing_candidate("my_task"))
        self.assertEqual(result["task_id"], "my_task")


class TestBuildLaneSummary(unittest.TestCase):
    def _passing_candidate(self, task_id: str) -> dict:
        return {
            "task_id": task_id,
            "dominant_stage_subtype": "stage_4_initialization_singularity",
            "dual_layer_mutation": True,
            "marker_only_repair": False,
            "planner_invoked": True,
            "resolution_path": "llm_planner_assisted",
        }

    def test_empty_input(self):
        summary = build_lane_summary([])
        self.assertEqual(summary["lane_status"], "EMPTY")
        self.assertEqual(summary["admitted_count"], 0)

    def test_below_minimum(self):
        candidates = [self._passing_candidate(f"t{i}") for i in range(MIN_CANDIDATE_READY_COUNT - 1)]
        summary = build_lane_summary(candidates)
        self.assertEqual(summary["lane_status"], "BELOW_MINIMUM")

    def test_candidate_ready(self):
        candidates = [self._passing_candidate(f"t{i}") for i in range(MIN_CANDIDATE_READY_COUNT)]
        summary = build_lane_summary(candidates)
        self.assertIn(summary["lane_status"], {"CANDIDATE_READY", "FREEZE_READY"})

    def test_freeze_ready(self):
        candidates = [self._passing_candidate(f"t{i}") for i in range(MIN_FREEZE_READY_COUNT)]
        summary = build_lane_summary(candidates)
        self.assertEqual(summary["lane_status"], "FREEZE_READY")

    def test_composition_fail_when_too_many_deterministic(self):
        # Build a mix: majority deterministic-only
        det = {
            "task_id": "det",
            "dominant_stage_subtype": "stage_4_initialization_singularity",
            "dual_layer_mutation": True,
            "marker_only_repair": False,
            "planner_invoked": False,
            "resolution_path": "deterministic_rule_only",
            "rounds_used": 3,
            "llm_request_count": 1,  # needed to pass planner gate via multi_round
        }
        # 7 deterministic_rule_only but passes planner gate via llm_request_count
        candidates = []
        for i in range(7):
            c = dict(det)
            c["task_id"] = f"det_{i}"
            candidates.append(c)
        # 3 planner-invoked
        for i in range(3):
            candidates.append(self._passing_candidate(f"plan_{i}"))
        # 10 total admitted, 70% deterministic → composition fail (> 40%)
        summary = build_lane_summary(candidates)
        if summary["admitted_count"] >= MIN_CANDIDATE_READY_COUNT:
            self.assertEqual(summary["lane_status"], "COMPOSITION_FAIL")

    def test_rejection_summary_populated(self):
        bad = {
            "task_id": "bad",
            "dominant_stage_subtype": "stage_2_structural_balance_reference",
            "declared_failure_type": "coupled_conflict_failure",
        }
        summary = build_lane_summary([bad])
        self.assertGreater(len(summary["rejection_summary"]), 0)

    def test_schema_version_present(self):
        summary = build_lane_summary([])
        self.assertIn("schema_version", summary)
        self.assertIn("generated_at_utc", summary)


if __name__ == "__main__":
    unittest.main()
