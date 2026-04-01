"""Tests for Layer 4 Guided Search Engine.

All tests are pure-function tests: no Docker, LLM, OMC, or filesystem
dependencies.  Organised by function, roughly following the module order.
"""
from __future__ import annotations

import unittest

from gateforge.agent_modelica_l4_guided_search_engine_v1 import (
    adaptive_parameter_target_pools,
    apply_behavioral_robustness_source_blind_local_repair,
    apply_simulate_error_parameter_recovery,
    apply_source_blind_multistep_branch_escape_search,
    apply_source_blind_multistep_exposure_repair,
    apply_source_blind_multistep_llm_plan,
    apply_source_blind_multistep_llm_resolution,
    apply_source_blind_multistep_local_search,
    apply_source_blind_multistep_stage2_local_repair,
    behavioral_robustness_local_repair_clusters,
    build_adaptive_search_candidates,
    build_guided_search_execution_plan,
    build_guided_search_observation_payload,
    guard_robustness_patch,
    llm_plan_branch_match,
    llm_plan_parameter_match,
    normalize_source_blind_multistep_llm_plan,
    preferred_llm_parameter_order_for_branch,
    resolve_llm_plan_parameter_names,
    robustness_structure_signature,
    select_initial_llm_plan_parameters,
    source_blind_multistep_branch_escape_templates,
    source_blind_multistep_exposure_clusters,
    source_blind_multistep_llm_resolution_targets,
    source_blind_multistep_local_search_templates,
    source_blind_multistep_stage2_resolution_clusters,
)
from gateforge.agent_modelica_text_repair_utils_v1 import (
    apply_regex_replacement_cluster,
    extract_named_numeric_values,
    find_primary_model_name,
    format_numeric_candidate,
)


# ===================================================================
# Shared text-repair utils
# ===================================================================


class TestFindPrimaryModelName(unittest.TestCase):
    def test_standard_model(self) -> None:
        self.assertEqual(find_primary_model_name("model Foo\nend Foo;"), "Foo")

    def test_partial_model(self) -> None:
        self.assertEqual(find_primary_model_name("partial model Bar\nend Bar;"), "Bar")

    def test_no_model(self) -> None:
        self.assertEqual(find_primary_model_name("class Baz\nend Baz;"), "")

    def test_empty(self) -> None:
        self.assertEqual(find_primary_model_name(""), "")

    def test_none(self) -> None:
        # noinspection PyTypeChecker
        self.assertEqual(find_primary_model_name(None), "")  # type: ignore[arg-type]


class TestFormatNumericCandidate(unittest.TestCase):
    def test_integer(self) -> None:
        self.assertEqual(format_numeric_candidate(1.0), "1")

    def test_float(self) -> None:
        self.assertEqual(format_numeric_candidate(0.5), "0.5")

    def test_small_decimal(self) -> None:
        self.assertEqual(format_numeric_candidate(0.123456), "0.123456")

    def test_zero(self) -> None:
        self.assertEqual(format_numeric_candidate(0.0), "0")

    def test_large_integer(self) -> None:
        self.assertEqual(format_numeric_candidate(40.0), "40")


class TestExtractNamedNumericValues(unittest.TestCase):
    def test_basic(self) -> None:
        text = "  parameter Real k = 1.5;\n  parameter Real startTime = 0.2;"
        result = extract_named_numeric_values(current_text=text, names=["k", "startTime"])
        self.assertEqual(result, {"k": "1.5", "startTime": "0.2"})

    def test_missing_name(self) -> None:
        text = "  parameter Real k = 1.0;"
        result = extract_named_numeric_values(current_text=text, names=["k", "missing"])
        self.assertEqual(result, {"k": "1.0"})

    def test_empty(self) -> None:
        result = extract_named_numeric_values(current_text="", names=["x"])
        self.assertEqual(result, {})


class TestApplyRegexReplacementCluster(unittest.TestCase):
    def test_applies(self) -> None:
        text = "k=1.18"
        patched, audit = apply_regex_replacement_cluster(
            current_text=text,
            cluster_name="test_cluster",
            replacements=[(r"k=1\.18", "k=1")],
        )
        self.assertEqual(patched, "k=1")
        self.assertTrue(audit["applied"])
        self.assertEqual(audit["cluster_name"], "test_cluster")

    def test_not_applicable(self) -> None:
        _, audit = apply_regex_replacement_cluster(
            current_text="k=1",
            cluster_name="test_cluster",
            replacements=[(r"k=999", "k=0")],
        )
        self.assertFalse(audit["applied"])


# ===================================================================
# adaptive_parameter_target_pools
# ===================================================================


class TestAdaptiveParameterTargetPools(unittest.TestCase):
    def test_stage_1_stability(self) -> None:
        pools = adaptive_parameter_target_pools(
            failure_type="stability_then_behavior",
            current_stage="stage_1",
            current_fail_bucket="",
        )
        self.assertTrue(len(pools) > 0)
        names = [p[0] for p in pools]
        self.assertIn("duration", names)
        self.assertIn("height", names)

    def test_stage_2_single_case(self) -> None:
        pools = adaptive_parameter_target_pools(
            failure_type="",
            current_stage="stage_2",
            current_fail_bucket="single_case_only",
        )
        self.assertTrue(len(pools) > 0)
        names = [p[0] for p in pools]
        self.assertIn("k", names)

    def test_unknown_returns_empty(self) -> None:
        pools = adaptive_parameter_target_pools(
            failure_type="unknown",
            current_stage="stage_3",
            current_fail_bucket="",
        )
        self.assertEqual(pools, [])


# ===================================================================
# build_adaptive_search_candidates
# ===================================================================


class TestBuildAdaptiveSearchCandidates(unittest.TestCase):
    def _model_text(self, **kw: float) -> str:
        lines = ["model PlantB"]
        for name, value in kw.items():
            lines.append(f"  parameter Real {name} = {value};")
        lines.append("end PlantB;")
        return "\n".join(lines)

    def test_produces_candidates(self) -> None:
        text = self._model_text(height=1.2, duration=1.1, k=1.18, startTime=0.8)
        candidates = build_adaptive_search_candidates(
            current_text=text,
            failure_type="stability_then_behavior",
            current_stage="stage_1",
            current_fail_bucket="",
            search_memory={},
            search_kind="stage_1_unlock",
        )
        self.assertTrue(len(candidates) > 0)
        self.assertIn("candidate_rank", candidates[0])
        self.assertIn("candidate_pool_size", candidates[0])

    def test_deduplicates_tried_keys(self) -> None:
        text = self._model_text(height=1.2, duration=1.1)
        first = build_adaptive_search_candidates(
            current_text=text,
            failure_type="stability_then_behavior",
            current_stage="stage_1",
            current_fail_bucket="",
            search_memory={},
            search_kind="stage_1_unlock",
        )
        tried = [c["candidate_key"] for c in first]
        second = build_adaptive_search_candidates(
            current_text=text,
            failure_type="stability_then_behavior",
            current_stage="stage_1",
            current_fail_bucket="",
            search_memory={"tried_candidate_values": tried},
            search_kind="stage_1_unlock",
        )
        second_keys = {c["candidate_key"] for c in second}
        for key in tried:
            self.assertNotIn(key, second_keys)

    def test_empty_for_unknown_failure(self) -> None:
        text = self._model_text(k=1.0)
        candidates = build_adaptive_search_candidates(
            current_text=text,
            failure_type="unknown_type",
            current_stage="stage_1",
            current_fail_bucket="",
            search_memory={},
            search_kind="test",
        )
        self.assertEqual(candidates, [])


class TestApplySimulateErrorParameterRecovery(unittest.TestCase):
    def test_recovers_zero_parameter_by_increase_direction(self) -> None:
        text = (
            "model DualLayerRC\n"
            "  parameter Real R = 0.0;\n"
            "  parameter Real C = 0.001;\n"
            "equation\n"
            "  R * C * der(v) = -v;\n"
            "end DualLayerRC;\n"
        )
        patched, audit = apply_simulate_error_parameter_recovery(
            current_text=text,
            llm_plan={"candidate_parameters": ["R"], "candidate_value_directions": ["increase"]},
            simulate_error_message="division by zero",
            search_memory={},
        )
        self.assertTrue(audit.get("applied"))
        self.assertIn("R=1", str(audit.get("candidate_values") or []))
        self.assertIn("parameter Real R = 1;", patched)

    def test_recovers_negative_initial_equation_by_increase_direction(self) -> None:
        text = (
            "model DualLayerLogOsc\n"
            "  Real y(start = 2.0);\n"
            "initial equation\n"
            "  y = -(2.0);\n"
            "equation\n"
            "  der(y) = -log(y) * y;\n"
            "end DualLayerLogOsc;\n"
        )
        patched, audit = apply_simulate_error_parameter_recovery(
            current_text=text,
            llm_plan={"candidate_parameters": ["y"], "candidate_value_directions": ["increase"]},
            simulate_error_message="initialization failed",
            search_memory={},
        )
        self.assertTrue(audit.get("applied"))
        self.assertIn("y = 2;", patched)

    def test_skips_tried_candidate_keys(self) -> None:
        text = "model A\n  parameter Real R = 0.0;\nend A;\n"
        patched, audit = apply_simulate_error_parameter_recovery(
            current_text=text,
            llm_plan={"candidate_parameters": ["R"], "candidate_value_directions": ["increase"]},
            simulate_error_message="division by zero",
            search_memory={"tried_candidate_values": ["simulate_error_parameter_recovery:R:1"]},
        )
        self.assertTrue(audit.get("applied"))
        self.assertNotEqual(str(audit.get("target_value") or ""), "1")


# ===================================================================
# source_blind_multistep_local_search_templates
# ===================================================================


class TestLocalSearchTemplates(unittest.TestCase):
    def test_stage_1_stability(self) -> None:
        templates = source_blind_multistep_local_search_templates(
            model_name="plantb",
            failure_type="stability_then_behavior",
            current_stage="stage_1",
            current_fail_bucket="",
        )
        self.assertTrue(len(templates) > 0)
        names = [t[0] for t in templates]
        self.assertIn("stage1_stability_behavior_unlock", names)

    def test_stage_2_recovery(self) -> None:
        templates = source_blind_multistep_local_search_templates(
            model_name="hybridb",
            failure_type="",
            current_stage="stage_2",
            current_fail_bucket="post_switch_recovery_miss",
        )
        names = [t[0] for t in templates]
        self.assertIn("stage2_recovery_hybridb_full", names)

    def test_non_hybridb_filters(self) -> None:
        templates = source_blind_multistep_local_search_templates(
            model_name="planta",
            failure_type="",
            current_stage="stage_2",
            current_fail_bucket="post_switch_recovery_miss",
        )
        names = [t[0] for t in templates]
        self.assertNotIn("stage2_recovery_hybridb_full", names)


# ===================================================================
# source_blind_multistep_branch_escape_templates
# ===================================================================


class TestBranchEscapeTemplates(unittest.TestCase):
    def test_neighbor_overfit_plantb(self) -> None:
        templates = source_blind_multistep_branch_escape_templates(
            model_name="plantb",
            failure_type="stability_then_behavior",
            current_branch="neighbor_overfit_trap",
        )
        self.assertTrue(len(templates) > 0)

    def test_unknown_branch_empty(self) -> None:
        templates = source_blind_multistep_branch_escape_templates(
            model_name="planta",
            failure_type="stability_then_behavior",
            current_branch="unknown_branch",
        )
        self.assertEqual(templates, [])


# ===================================================================
# apply_source_blind_multistep_branch_escape_search
# ===================================================================


class TestApplyBranchEscapeSearch(unittest.TestCase):
    def test_unsupported_branch(self) -> None:
        _, audit = apply_source_blind_multistep_branch_escape_search(
            current_text="model Foo\nend Foo;",
            declared_failure_type="stability_then_behavior",
            current_branch="some_branch",
            preferred_branch="other",
            search_memory={},
        )
        self.assertFalse(audit["applied"])
        self.assertEqual(audit["reason"], "branch_escape_not_supported")

    def test_applies_to_plantb(self) -> None:
        text = "model PlantB\n  parameter Real startTime = 0.8;\nend PlantB;"
        patched, audit = apply_source_blind_multistep_branch_escape_search(
            current_text=text,
            declared_failure_type="stability_then_behavior",
            current_branch="neighbor_overfit_trap",
            preferred_branch="behavior_timing_branch",
            search_memory={},
        )
        self.assertTrue(audit["applied"])
        self.assertIn("startTime=0.2", patched)


# ===================================================================
# apply_source_blind_multistep_local_search
# ===================================================================


class TestApplyLocalSearch(unittest.TestCase):
    def test_unsupported_failure_type(self) -> None:
        _, audit = apply_source_blind_multistep_local_search(
            current_text="model Foo\nend Foo;",
            declared_failure_type="unknown",
            current_stage="stage_1",
            current_fail_bucket="",
            search_memory={},
        )
        self.assertFalse(audit["applied"])

    def test_applies_adaptive_search(self) -> None:
        text = "model PlantB\n  parameter Real height = 1.2;\n  parameter Real duration = 1.1;\nend PlantB;"
        patched, audit = apply_source_blind_multistep_local_search(
            current_text=text,
            declared_failure_type="stability_then_behavior",
            current_stage="stage_1",
            current_fail_bucket="",
            search_memory={},
        )
        self.assertTrue(audit["applied"])


# ===================================================================
# behavioral_robustness_local_repair_clusters
# ===================================================================


class TestBehavioralRobustnessLocalRepairClusters(unittest.TestCase):
    def test_param_perturbation(self) -> None:
        clusters = behavioral_robustness_local_repair_clusters(
            model_name="switcha",
            failure_type="param_perturbation_robustness_violation",
        )
        self.assertTrue(len(clusters) > 0)
        names = [c[0] for c in clusters]
        self.assertIn("switcha_width_period_cluster", names)

    def test_model_specific_prepend(self) -> None:
        clusters = behavioral_robustness_local_repair_clusters(
            model_name="planta",
            failure_type="initial_condition_robustness_violation",
        )
        self.assertTrue(clusters[0][0] == "planta_cluster")

    def test_unknown_failure(self) -> None:
        clusters = behavioral_robustness_local_repair_clusters(
            model_name="planta",
            failure_type="unknown_failure",
        )
        self.assertEqual(clusters, [])


# ===================================================================
# apply_behavioral_robustness_source_blind_local_repair
# ===================================================================


class TestApplyBehavioralRobustnessSourceBlindLocalRepair(unittest.TestCase):
    def test_disabled(self) -> None:
        _, audit = apply_behavioral_robustness_source_blind_local_repair(
            current_text="model Foo\nend Foo;",
            declared_failure_type="param_perturbation_robustness_violation",
            current_round=1,
            robustness_repair_enabled=False,
            source_mode="source_blind",
        )
        self.assertFalse(audit["applied"])

    def test_wrong_mode(self) -> None:
        _, audit = apply_behavioral_robustness_source_blind_local_repair(
            current_text="model Foo\nend Foo;",
            declared_failure_type="param_perturbation_robustness_violation",
            current_round=1,
            robustness_repair_enabled=True,
            source_mode="source_aware",
        )
        self.assertFalse(audit["applied"])

    def test_applies_cluster(self) -> None:
        text = "model SwitchA\n  parameter Real k = 1.18;\nend SwitchA;"
        patched, audit = apply_behavioral_robustness_source_blind_local_repair(
            current_text=text,
            declared_failure_type="param_perturbation_robustness_violation",
            current_round=1,
            robustness_repair_enabled=True,
            source_mode="source_blind",
        )
        self.assertTrue(audit["applied"])
        self.assertIn("k=1", patched)


# ===================================================================
# source_blind_multistep_exposure_clusters
# ===================================================================


class TestExposureClusters(unittest.TestCase):
    def test_plantb_stability(self) -> None:
        clusters = source_blind_multistep_exposure_clusters(
            model_name="plantb",
            failure_type="stability_then_behavior",
        )
        self.assertEqual(len(clusters), 1)
        self.assertIn("plantb", clusters[0][0])

    def test_unknown_model(self) -> None:
        clusters = source_blind_multistep_exposure_clusters(
            model_name="unknown_model",
            failure_type="stability_then_behavior",
        )
        self.assertEqual(clusters, [])


# ===================================================================
# apply_source_blind_multistep_exposure_repair
# ===================================================================


class TestApplyExposureRepair(unittest.TestCase):
    def test_only_round_1(self) -> None:
        _, audit = apply_source_blind_multistep_exposure_repair(
            current_text="model PlantB\nend PlantB;",
            declared_failure_type="stability_then_behavior",
            current_round=2,
        )
        self.assertFalse(audit["applied"])
        self.assertEqual(audit["reason"], "exposure_repair_only_runs_in_round_1")

    def test_applies_round_1(self) -> None:
        text = "model PlantB\n  parameter Real height = 1.2;\n  parameter Real duration = 1.1;\nend PlantB;"
        patched, audit = apply_source_blind_multistep_exposure_repair(
            current_text=text,
            declared_failure_type="stability_then_behavior",
            current_round=1,
        )
        self.assertTrue(audit["applied"])


# ===================================================================
# source_blind_multistep_stage2_resolution_clusters
# ===================================================================


class TestStage2ResolutionClusters(unittest.TestCase):
    def test_known_entry(self) -> None:
        clusters = source_blind_multistep_stage2_resolution_clusters(
            model_name="planta",
            failure_type="stability_then_behavior",
            fail_bucket="behavior_contract_miss",
        )
        self.assertEqual(len(clusters), 1)

    def test_unknown_entry(self) -> None:
        clusters = source_blind_multistep_stage2_resolution_clusters(
            model_name="unknown",
            failure_type="unknown",
            fail_bucket="unknown",
        )
        self.assertEqual(clusters, [])


# ===================================================================
# apply_source_blind_multistep_stage2_local_repair
# ===================================================================


class TestApplyStage2LocalRepair(unittest.TestCase):
    def test_requires_stage_2(self) -> None:
        _, audit = apply_source_blind_multistep_stage2_local_repair(
            current_text="model Foo\nend Foo;",
            declared_failure_type="stability_then_behavior",
            current_stage="stage_1",
            current_fail_bucket="behavior_contract_miss",
            current_round=2,
        )
        self.assertFalse(audit["applied"])
        self.assertEqual(audit["reason"], "stage_2_local_repair_requires_stage_2")


# ===================================================================
# robustness_structure_signature / guard_robustness_patch
# ===================================================================


class TestRobustnessStructureSignature(unittest.TestCase):
    def test_captures_connect(self) -> None:
        text = "  connect(a.y, b.u);\n  // comment\n"
        sigs = robustness_structure_signature(text)
        self.assertEqual(sigs, ["connect(a.y, b.u);"])

    def test_captures_blocks(self) -> None:
        text = "  Modelica.Blocks.Sources.Step step1(height=1);\n"
        sigs = robustness_structure_signature(text)
        self.assertEqual(len(sigs), 1)

    def test_empty(self) -> None:
        self.assertEqual(robustness_structure_signature(""), [])


class TestGuardRobustnessPatch(unittest.TestCase):
    def test_non_robustness_passes(self) -> None:
        result, audit = guard_robustness_patch(
            original_text="model X\nend X;",
            patched_text="model X\n// patched\nend X;",
            failure_type="connector_mismatch",
        )
        self.assertEqual(result, "model X\n// patched\nend X;")
        self.assertTrue(audit["accepted"])

    def test_empty_patch_rejected(self) -> None:
        result, audit = guard_robustness_patch(
            original_text="model X\nend X;",
            patched_text="   ",
            failure_type="stability_then_behavior",
        )
        self.assertIsNone(result)
        self.assertFalse(audit["accepted"])

    def test_forbidden_threshold(self) -> None:
        result, audit = guard_robustness_patch(
            original_text="model X\n  parameter Real k = 1;\nend X;",
            patched_text="model X\n  parameter Real k = 1;\n  parameter Real threshold=0.5;\nend X;",
            failure_type="stability_then_behavior",
        )
        self.assertIsNone(result)
        self.assertFalse(audit["accepted"])

    def test_structure_drift_rejected(self) -> None:
        original = "model X\n  connect(a.y, b.u);\nend X;"
        patched = "model X\n  connect(a.y, c.u);\nend X;"
        result, audit = guard_robustness_patch(
            original_text=original,
            patched_text=patched,
            failure_type="stability_then_behavior",
        )
        self.assertIsNone(result)
        self.assertFalse(audit["accepted"])

    def test_parameter_only_change_accepted(self) -> None:
        original = "model X\n  parameter Real k = 1.18;\n  connect(a.y, b.u);\nend X;"
        patched = "model X\n  parameter Real k = 1;\n  connect(a.y, b.u);\nend X;"
        result, audit = guard_robustness_patch(
            original_text=original,
            patched_text=patched,
            failure_type="stability_then_behavior",
        )
        self.assertEqual(result, patched)
        self.assertTrue(audit["accepted"])


# ===================================================================
# source_blind_multistep_llm_resolution_targets
# ===================================================================


class TestLlmResolutionTargets(unittest.TestCase):
    def test_known_entry(self) -> None:
        targets = source_blind_multistep_llm_resolution_targets(
            model_name="planta",
            failure_type="stability_then_behavior",
        )
        self.assertIn("k", targets)
        self.assertEqual(targets["k"], 1.0)

    def test_unknown(self) -> None:
        targets = source_blind_multistep_llm_resolution_targets(
            model_name="unknown",
            failure_type="unknown",
        )
        self.assertEqual(targets, {})


# ===================================================================
# preferred_llm_parameter_order_for_branch
# ===================================================================


class TestPreferredLlmParameterOrder(unittest.TestCase):
    def test_known_preference(self) -> None:
        order = preferred_llm_parameter_order_for_branch(
            failure_type="stability_then_behavior",
            branch_name="behavior_timing_branch",
            available_targets={"startTime": 0.2, "k": 1.0, "height": 1.0},
        )
        self.assertEqual(order[0], "startTime")

    def test_unknown_branch_returns_all(self) -> None:
        order = preferred_llm_parameter_order_for_branch(
            failure_type="unknown",
            branch_name="unknown",
            available_targets={"a": 1.0, "b": 2.0},
        )
        self.assertEqual(set(order), {"a", "b"})


# ===================================================================
# normalize_source_blind_multistep_llm_plan
# ===================================================================


class TestNormalizeLlmPlan(unittest.TestCase):
    def test_basic_normalization(self) -> None:
        result = normalize_source_blind_multistep_llm_plan(
            payload={
                "candidate_parameters": ["k", "startTime"],
                "switch_to_branch": "behavior_timing_branch",
                "replan_budget_for_resolution": 2,
            },
            stage_context={"current_stage": "stage_2", "stage_2_branch": "trap"},
            llm_reason="test_reason",
        )
        self.assertEqual(result["candidate_parameters"], ["k", "startTime"])
        self.assertEqual(result["switch_to_branch"], "behavior_timing_branch")
        self.assertEqual(result["replan_budget_for_resolution"], 2)

    def test_none_payload(self) -> None:
        result = normalize_source_blind_multistep_llm_plan(
            payload=None,
            stage_context={},
            llm_reason="fallback",
        )
        self.assertEqual(result["candidate_parameters"], [])
        self.assertEqual(result["repair_goal"], "fallback")

    def test_bucket_alias_resolution(self) -> None:
        result = normalize_source_blind_multistep_llm_plan(
            payload={
                "guided_search_bucket_sequence": ["diagnosis", "escape", "resolve"],
                "replan_budget_for_branch_diagnosis": 1,
            },
            stage_context={},
            llm_reason="test",
        )
        self.assertEqual(
            result["guided_search_bucket_sequence"],
            ["branch_diagnosis", "branch_escape", "resolution"],
        )


# ===================================================================
# build_guided_search_execution_plan
# ===================================================================


class TestBuildGuidedSearchExecutionPlan(unittest.TestCase):
    def test_basic_plan(self) -> None:
        plan = build_guided_search_execution_plan(
            llm_plan={
                "replan_budget_for_branch_diagnosis": 1,
                "replan_budget_for_branch_escape": 1,
                "replan_budget_for_resolution": 2,
                "guided_search_bucket_sequence": ["branch_diagnosis", "branch_escape", "resolution"],
            },
            stage_context={
                "stage_2_branch": "trap_branch",
                "preferred_stage_2_branch": "good_branch",
                "trap_branch": True,
            },
            requested_parameters=["k", "startTime", "height"],
            ordered_targets=["k", "startTime", "height"],
            previous_branch="",
        )
        self.assertEqual(plan["execution_parameters"], ["k", "startTime"])
        self.assertEqual(plan["candidate_suppressed_by_budget"], 1)
        self.assertFalse(plan["branch_escape_skipped_due_to_budget"])

    def test_zero_budget(self) -> None:
        plan = build_guided_search_execution_plan(
            llm_plan={
                "replan_budget_for_branch_diagnosis": 0,
                "replan_budget_for_branch_escape": 0,
                "replan_budget_for_resolution": 0,
                "guided_search_bucket_sequence": [],
            },
            stage_context={},
            requested_parameters=["k"],
            ordered_targets=["k"],
            previous_branch="",
        )
        self.assertEqual(plan["execution_parameters"], [])
        self.assertTrue(plan["resolution_skipped_due_to_budget"])


# ===================================================================
# build_guided_search_observation_payload
# ===================================================================


class TestBuildGuidedSearchObservationPayload(unittest.TestCase):
    def test_basic_observation(self) -> None:
        obs = build_guided_search_observation_payload(
            memory={
                "last_budget_spent_by_bucket": {"resolution": 2},
                "last_candidate_attempt_count_by_bucket": {"resolution": 2},
                "last_guided_search_bucket_sequence": ["resolution"],
                "last_llm_plan_pass_count": 1,
            },
            stage_context={
                "stage_2_branch": "good_branch",
                "preferred_stage_2_branch": "good_branch",
                "branch_mode": "preferred",
                "current_stage": "stage_2",
            },
            contract_fail_bucket="single_case_only",
            scenario_results=[
                {"scenario_id": "s1", "pass": True},
                {"scenario_id": "s2", "pass": True},
                {"scenario_id": "s3", "pass": True},
            ],
        )
        self.assertEqual(obs["best_progress_by_bucket"]["resolution"], 2)
        self.assertEqual(obs["best_progress_by_bucket"]["branch_escape"], 1)
        self.assertFalse(obs["branch_regression_seen"])


# ===================================================================
# resolve_llm_plan_parameter_names
# ===================================================================


class TestResolveLlmPlanParameterNames(unittest.TestCase):
    def test_direct_match(self) -> None:
        result = resolve_llm_plan_parameter_names(
            requested_names=["k", "startTime"],
            available_targets={"k": 1.0, "startTime": 0.2},
        )
        self.assertEqual(result, ["k", "startTime"])

    def test_alias_f(self) -> None:
        result = resolve_llm_plan_parameter_names(
            requested_names=["f"],
            available_targets={"freqHz": 1.0},
        )
        self.assertEqual(result, ["freqHz"])

    def test_dotted_name(self) -> None:
        result = resolve_llm_plan_parameter_names(
            requested_names=["step1.startTime"],
            available_targets={"startTime": 0.2},
        )
        self.assertEqual(result, ["startTime"])

    def test_no_match(self) -> None:
        result = resolve_llm_plan_parameter_names(
            requested_names=["nonexistent"],
            available_targets={"k": 1.0},
        )
        self.assertEqual(result, [])


# ===================================================================
# select_initial_llm_plan_parameters
# ===================================================================


class TestSelectInitialLlmPlanParameters(unittest.TestCase):
    def test_forces_start_freq(self) -> None:
        result = select_initial_llm_plan_parameters(
            llm_plan={"candidate_parameters": ["startTime", "freqHz", "k"]},
            available_targets={"startTime": 0.3, "freqHz": 1.0, "k": 0.5},
            failure_type="behavior_then_robustness",
        )
        self.assertEqual(result, ["startTime", "freqHz"])

    def test_fallback_to_branch_preference(self) -> None:
        result = select_initial_llm_plan_parameters(
            llm_plan={"candidate_parameters": [], "preferred_branch": "behavior_timing_branch"},
            available_targets={"startTime": 0.2, "k": 1.0},
            failure_type="stability_then_behavior",
        )
        self.assertEqual(len(result), 1)


# ===================================================================
# llm_plan_branch_match / llm_plan_parameter_match
# ===================================================================


class TestLlmPlanBranchMatch(unittest.TestCase):
    def test_match(self) -> None:
        self.assertTrue(llm_plan_branch_match(
            llm_plan={"preferred_branch": "behavior_timing_branch"},
            stage_context={"preferred_stage_2_branch": "behavior_timing_branch"},
        ))

    def test_no_match(self) -> None:
        self.assertFalse(llm_plan_branch_match(
            llm_plan={"preferred_branch": "wrong_branch"},
            stage_context={"preferred_stage_2_branch": "behavior_timing_branch"},
        ))


class TestLlmPlanParameterMatch(unittest.TestCase):
    def test_match(self) -> None:
        self.assertTrue(llm_plan_parameter_match(
            llm_plan={"candidate_parameters": ["k"]},
            available_targets={"k": 1.0, "startTime": 0.2},
        ))

    def test_no_match(self) -> None:
        self.assertFalse(llm_plan_parameter_match(
            llm_plan={"candidate_parameters": ["nonexistent"]},
            available_targets={"k": 1.0},
        ))


# ===================================================================
# apply_source_blind_multistep_llm_plan
# ===================================================================


class TestApplyLlmPlan(unittest.TestCase):
    def test_applies(self) -> None:
        text = "model PlantA\n  parameter Real k = 1.18;\n  parameter Real height = 1.12;\nend PlantA;"
        patched, audit = apply_source_blind_multistep_llm_plan(
            current_text=text,
            declared_failure_type="stability_then_behavior",
            llm_plan={"candidate_parameters": ["k", "height"]},
            llm_reason="test_plan",
        )
        self.assertTrue(audit["applied"])
        self.assertIn("k=1", patched)

    def test_no_targets(self) -> None:
        _, audit = apply_source_blind_multistep_llm_plan(
            current_text="model Unknown\nend Unknown;",
            declared_failure_type="stability_then_behavior",
            llm_plan={},
            llm_reason="test",
        )
        self.assertFalse(audit["applied"])


# ===================================================================
# apply_source_blind_multistep_llm_resolution
# ===================================================================


class TestApplyLlmResolution(unittest.TestCase):
    def test_applies_all_targets(self) -> None:
        text = "model PlantA\n  parameter Real k = 1.18;\n  parameter Real height = 1.12;\n  parameter Real startTime = 0.8;\nend PlantA;"
        patched, audit = apply_source_blind_multistep_llm_resolution(
            current_text=text,
            declared_failure_type="stability_then_behavior",
            llm_reason="forced",
        )
        self.assertTrue(audit["applied"])
        self.assertIn("k=1", patched)
        self.assertIn("height=1", patched)
        self.assertIn("startTime=0.1", patched)

    def test_already_satisfied(self) -> None:
        text = "model PlantA\n  parameter Real k = 1;\n  parameter Real height = 1;\n  parameter Real startTime = 0.1;\nend PlantA;"
        _, audit = apply_source_blind_multistep_llm_resolution(
            current_text=text,
            declared_failure_type="stability_then_behavior",
            llm_reason="forced",
        )
        self.assertFalse(audit["applied"])


if __name__ == "__main__":
    unittest.main()
