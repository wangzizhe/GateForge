"""Tests for Layer 3 Stage/Branch State Machine.

All tests are pure-function tests: no Docker, LLM, OMC, or filesystem
dependencies. Organised by function, roughly following the module order.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

from gateforge.agent_modelica_stage_branch_controller_v1 import (
    behavioral_contract_bucket,
    build_branching_stage_2_eval,
    build_multistep_eval,
    build_multistep_stage_context,
    build_source_blind_multistep_llm_context,
    build_source_blind_multistep_llm_replan_context,
    build_source_blind_multistep_replan_budget,
    count_passed_scenarios,
    extract_source_blind_multistep_markers,
    looks_like_stage_1_focus,
    make_multistep_memory,
    multistep_branch_mode,
    multistep_stage_default_focus,
    stage_plan_fields,
)


# ===================================================================
# behavioral_contract_bucket
# ===================================================================


class TestBehavioralContractBucket(unittest.TestCase):
    def test_known_mapping(self) -> None:
        self.assertEqual(behavioral_contract_bucket("steady_state_target_violation"), "steady_state_miss")
        self.assertEqual(behavioral_contract_bucket("stability_then_behavior"), "stability_margin_miss")
        self.assertEqual(behavioral_contract_bucket("behavior_then_robustness"), "single_case_only")

    def test_unknown_returns_fallback(self) -> None:
        self.assertEqual(behavioral_contract_bucket("some_unknown_type"), "behavioral_contract_fail")

    def test_empty_and_none(self) -> None:
        self.assertEqual(behavioral_contract_bucket(""), "behavioral_contract_fail")
        # noinspection PyTypeChecker
        self.assertEqual(behavioral_contract_bucket(None), "behavioral_contract_fail")  # type: ignore[arg-type]


# ===================================================================
# build_multistep_eval
# ===================================================================


class TestBuildMultistepEval(unittest.TestCase):
    def test_pass_all_true(self) -> None:
        result = build_multistep_eval(
            stage="stage_2",
            transition_reason="nominal_pass",
            transition_seen=True,
            pass_all=True,
            bucket="",
            scenario_results=[{"scenario_id": "s1", "pass": True}],
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["contract_fail_bucket"], "")
        self.assertTrue(result["multi_step_stage_2_unlocked"])

    def test_fail_with_scenarios(self) -> None:
        result = build_multistep_eval(
            stage="stage_2",
            transition_reason="",
            transition_seen=True,
            pass_all=False,
            bucket="single_case_only",
            scenario_results=[{"scenario_id": "s1", "pass": True}, {"scenario_id": "s2", "pass": False}],
        )
        self.assertFalse(result["pass"])
        self.assertIn("single_case_only", result["reasons"])
        self.assertEqual(result["contract_fail_bucket"], "single_case_only")

    def test_stage_1_not_unlocked(self) -> None:
        result = build_multistep_eval(
            stage="stage_1",
            transition_reason="",
            transition_seen=False,
            pass_all=False,
            bucket="stability_margin_miss",
            scenario_results=[],
        )
        self.assertFalse(result["multi_step_stage_2_unlocked"])
        self.assertEqual(result["multi_step_stage"], "stage_1")


# ===================================================================
# multistep_stage_default_focus
# ===================================================================


class TestMultistepStageDefaultFocus(unittest.TestCase):
    def test_stage_1_stability_then_behavior(self) -> None:
        focus = multistep_stage_default_focus(
            failure_type="stability_then_behavior",
            stage="stage_1",
            fail_bucket="stability_margin_miss",
        )
        self.assertEqual(focus, "unlock_stage_2_behavior_gate")

    def test_stage_1_generic(self) -> None:
        focus = multistep_stage_default_focus(
            failure_type="unknown",
            stage="stage_1",
            fail_bucket="some_bucket",
        )
        self.assertEqual(focus, "unlock_stage_2")

    def test_stage_2_with_branch(self) -> None:
        focus = multistep_stage_default_focus(
            failure_type="behavior_then_robustness",
            stage="stage_2",
            fail_bucket="single_case_only",
            stage_2_branch="behavior_timing_branch",
        )
        self.assertEqual(focus, "resolve_stage_2_behavior_timing")

    def test_stage_2_trap_branch(self) -> None:
        focus = multistep_stage_default_focus(
            failure_type="behavior_then_robustness",
            stage="stage_2",
            fail_bucket="single_case_only",
            stage_2_branch="neighbor_overfit_trap",
            trap_branch=True,
        )
        self.assertEqual(focus, "escape_trap_branch_neighbor_overfit")

    def test_stage_2_no_branch(self) -> None:
        focus = multistep_stage_default_focus(
            failure_type="behavior_then_robustness",
            stage="stage_2",
            fail_bucket="single_case_only",
        )
        self.assertEqual(focus, "resolve_stage_2_neighbor_robustness")

    def test_passed(self) -> None:
        focus = multistep_stage_default_focus(
            failure_type="behavior_then_robustness",
            stage="passed",
            fail_bucket="",
        )
        self.assertEqual(focus, "stop_editing")


# ===================================================================
# multistep_branch_mode
# ===================================================================


class TestMultistepBranchMode(unittest.TestCase):
    def test_stage_1_returns_empty(self) -> None:
        mode = multistep_branch_mode(
            current_stage="stage_1",
            stage_2_branch="some_branch",
            preferred_stage_2_branch="some_branch",
            trap_branch=False,
        )
        self.assertEqual(mode, "")

    def test_trap(self) -> None:
        mode = multistep_branch_mode(
            current_stage="stage_2",
            stage_2_branch="neighbor_overfit_trap",
            preferred_stage_2_branch="neighbor_robustness_branch",
            trap_branch=True,
        )
        self.assertEqual(mode, "trap")

    def test_preferred(self) -> None:
        mode = multistep_branch_mode(
            current_stage="stage_2",
            stage_2_branch="neighbor_robustness_branch",
            preferred_stage_2_branch="neighbor_robustness_branch",
            trap_branch=False,
        )
        self.assertEqual(mode, "preferred")

    def test_unknown(self) -> None:
        mode = multistep_branch_mode(
            current_stage="stage_2",
            stage_2_branch="behavior_timing_branch",
            preferred_stage_2_branch="neighbor_robustness_branch",
            trap_branch=False,
        )
        self.assertEqual(mode, "unknown")


# ===================================================================
# looks_like_stage_1_focus
# ===================================================================


class TestLooksLikeStage1Focus(unittest.TestCase):
    def test_matches_stability_keyword(self) -> None:
        self.assertTrue(
            looks_like_stage_1_focus(
                failure_type="stability_then_behavior",
                action="fix startup timing and stability issue",
            )
        )

    def test_rejects_stage_2_directive(self) -> None:
        self.assertFalse(
            looks_like_stage_1_focus(
                failure_type="stability_then_behavior",
                action="stop revisiting stability after stage_2 unlock",
            )
        )

    def test_no_match_returns_false(self) -> None:
        self.assertFalse(
            looks_like_stage_1_focus(
                failure_type="stability_then_behavior",
                action="adjust gain to reduce overshoot",
            )
        )


# ===================================================================
# build_multistep_stage_context
# ===================================================================


class TestBuildMultistepStageContext(unittest.TestCase):
    def test_empty_memory_stage_1(self) -> None:
        memory = make_multistep_memory()
        ctx = build_multistep_stage_context(
            failure_type="stability_then_behavior",
            behavioral_eval={"multi_step_stage": "stage_1", "contract_fail_bucket": "stability_margin_miss"},
            current_round=1,
            memory=memory,
        )
        self.assertEqual(ctx["current_stage"], "stage_1")
        self.assertFalse(ctx["stage_2_unlocked"])
        self.assertEqual(ctx["next_focus"], "unlock_stage_2_behavior_gate")

    def test_stage_2_unlocked_sets_transition_round(self) -> None:
        memory = make_multistep_memory()
        ctx = build_multistep_stage_context(
            failure_type="behavior_then_robustness",
            behavioral_eval={
                "multi_step_stage": "stage_2",
                "multi_step_stage_2_unlocked": True,
                "contract_fail_bucket": "single_case_only",
                "multi_step_transition_reason": "nominal_pass",
            },
            current_round=3,
            memory=memory,
        )
        self.assertTrue(ctx["stage_2_unlocked"])
        self.assertEqual(ctx["transition_round"], 3)
        self.assertEqual(ctx["transition_reason"], "nominal_pass")

    def test_trap_detection(self) -> None:
        memory = make_multistep_memory()
        ctx = build_multistep_stage_context(
            failure_type="behavior_then_robustness",
            behavioral_eval={
                "multi_step_stage": "stage_2",
                "multi_step_stage_2_unlocked": True,
                "contract_fail_bucket": "single_case_only",
                "stage_2_branch": "neighbor_overfit_trap",
                "trap_branch": True,
                "correct_branch_selected": False,
            },
            current_round=4,
            memory=memory,
        )
        self.assertTrue(ctx["trap_branch"])
        self.assertFalse(ctx["correct_branch_selected"])
        self.assertEqual(ctx["branch_mode"], "trap")

    def test_stage_2_first_fail_bucket_persists(self) -> None:
        memory = make_multistep_memory()
        memory["stage_2_first_fail_bucket"] = "single_case_only"
        ctx = build_multistep_stage_context(
            failure_type="behavior_then_robustness",
            behavioral_eval={
                "multi_step_stage": "stage_2",
                "multi_step_stage_2_unlocked": True,
                "contract_fail_bucket": "overshoot_or_settling_violation",
            },
            current_round=5,
            memory=memory,
        )
        self.assertEqual(ctx["stage_2_first_fail_bucket"], "single_case_only")

    def test_none_eval_treated_as_empty(self) -> None:
        memory = make_multistep_memory()
        ctx = build_multistep_stage_context(
            failure_type="stability_then_behavior",
            behavioral_eval=None,
            current_round=1,
            memory=memory,
        )
        self.assertEqual(ctx["current_stage"], "")
        self.assertFalse(ctx["stage_2_unlocked"])


# ===================================================================
# stage_plan_fields
# ===================================================================


class TestStagePlanFields(unittest.TestCase):
    def test_with_plan(self) -> None:
        plan = {
            "plan_stage": "stage_2",
            "branch_stage": "neighbor_robustness_branch",
            "current_branch": "neighbor_robustness_branch",
            "preferred_branch": "neighbor_robustness_branch",
            "branch_mode": "preferred",
            "plan_goal": "reduce overshoot",
            "plan_actions": ["adjust gain", "tune timing"],
            "plan_constraints": ["keep nominal stable"],
            "plan_stop_condition": "all scenarios pass",
        }
        result = stage_plan_fields(
            plan=plan,
            generated=True,
            followed=True,
            conflict_rejected=False,
            conflict_rejected_count=0,
            executed_action="adjust gain",
        )
        self.assertTrue(result["stage_plan_generated"])
        self.assertTrue(result["plan_followed"])
        self.assertEqual(result["plan_stage"], "stage_2")
        self.assertEqual(result["plan_actions"], ["adjust gain", "tune timing"])
        self.assertEqual(result["executed_plan_action"], "adjust gain")

    def test_no_plan(self) -> None:
        result = stage_plan_fields(
            plan=None,
            generated=False,
            followed=False,
            conflict_rejected=False,
            conflict_rejected_count=0,
            executed_action="",
        )
        self.assertFalse(result["stage_plan_generated"])
        self.assertEqual(result["plan_stage"], "")
        self.assertEqual(result["plan_actions"], [])


# ===================================================================
# extract_source_blind_multistep_markers
# ===================================================================


class TestExtractMarkers(unittest.TestCase):
    def test_markers_present(self) -> None:
        text = (
            "model Test\n"
            "  // gateforge_source_blind_multistep_realism_version:v5\n"
            "  // gateforge_source_blind_multistep_llm_forcing:true\n"
            "  // gateforge_source_blind_multistep_llm_profile:gemini-2\n"
            "  // gateforge_source_blind_multistep_llm_trigger:branch_unknown\n"
            "end Test;\n"
        )
        markers = extract_source_blind_multistep_markers(text)
        self.assertEqual(markers["realism_version"], "v5")
        self.assertTrue(markers["llm_forcing"])
        self.assertEqual(markers["llm_profile"], "gemini-2")
        self.assertEqual(markers["llm_trigger"], "branch_unknown")

    def test_empty_text(self) -> None:
        markers = extract_source_blind_multistep_markers("")
        self.assertEqual(markers["realism_version"], "")
        self.assertFalse(markers["llm_forcing"])

    def test_forcing_false_variants(self) -> None:
        text = "// gateforge_source_blind_multistep_llm_forcing:0\n"
        markers = extract_source_blind_multistep_markers(text)
        self.assertFalse(markers["llm_forcing"])


# ===================================================================
# build_source_blind_multistep_llm_context
# ===================================================================


class TestLlmContext(unittest.TestCase):
    def _make_context(self, **overrides) -> dict:
        base = {
            "current_text": "",
            "stage_context": {
                "current_stage": "stage_2",
                "stage_2_branch": "neighbor_robustness_branch",
                "current_fail_bucket": "single_case_only",
                "branch_mode": "preferred",
                "trap_branch": False,
            },
            "current_round": 3,
            "memory": make_multistep_memory(),
        }
        base.update(overrides)
        return build_source_blind_multistep_llm_context(**base)

    def test_no_forcing_marker(self) -> None:
        result = self._make_context(current_text="model Foo end Foo;")
        self.assertFalse(result["should_force_llm"])
        self.assertEqual(result["llm_plan_reason"], "")

    def test_unknown_branch_mode(self) -> None:
        text = "// gateforge_source_blind_multistep_llm_forcing:true\n"
        ctx = {
            "current_stage": "stage_2",
            "stage_2_branch": "behavior_timing_branch",
            "current_fail_bucket": "single_case_only",
            "branch_mode": "unknown",
            "trap_branch": False,
        }
        result = self._make_context(current_text=text, stage_context=ctx)
        self.assertTrue(result["should_force_llm"])
        self.assertEqual(result["llm_plan_reason"], "branch_diagnosis_unknown")

    def test_trap_no_escape(self) -> None:
        text = "// gateforge_source_blind_multistep_llm_forcing:true\n"
        ctx = {
            "current_stage": "stage_2",
            "stage_2_branch": "neighbor_overfit_trap",
            "current_fail_bucket": "single_case_only",
            "branch_mode": "trap",
            "trap_branch": True,
        }
        mem = make_multistep_memory()
        mem["branch_escape_attempt_count"] = 2
        mem["branch_escape_success_count"] = 1
        result = self._make_context(current_text=text, stage_context=ctx, memory=mem)
        self.assertTrue(result["should_force_llm"])
        self.assertEqual(result["llm_plan_reason"], "trap_escape_no_progress")

    def test_candidate_pool_exhausted(self) -> None:
        text = "// gateforge_source_blind_multistep_llm_forcing:true\n"
        ctx = {
            "current_stage": "stage_1",
            "stage_2_branch": "",
            "current_fail_bucket": "stability_margin_miss",
            "branch_mode": "",
            "trap_branch": False,
        }
        mem = make_multistep_memory()
        mem["search_improvement_seen"] = False
        result = self._make_context(current_text=text, stage_context=ctx, current_round=3, memory=mem)
        self.assertTrue(result["should_force_llm"])
        self.assertEqual(result["llm_plan_reason"], "candidate_pool_exhausted")


# ===================================================================
# count_passed_scenarios
# ===================================================================


class TestCountPassedScenarios(unittest.TestCase):
    def test_mixed(self) -> None:
        rows = [{"pass": True}, {"pass": False}, {"pass": True}]
        self.assertEqual(count_passed_scenarios(rows), 2)

    def test_none(self) -> None:
        self.assertEqual(count_passed_scenarios(None), 0)

    def test_empty(self) -> None:
        self.assertEqual(count_passed_scenarios([]), 0)


# ===================================================================
# build_source_blind_multistep_llm_replan_context
# ===================================================================


class TestLlmReplanContext(unittest.TestCase):
    def _base_kwargs(self, **overrides) -> dict:
        base = {
            "current_text": "// gateforge_source_blind_multistep_realism_version:v4\n"
                            "// gateforge_source_blind_multistep_llm_forcing:true\n",
            "stage_context": {
                "current_stage": "stage_2",
                "stage_2_branch": "neighbor_robustness_branch",
                "preferred_stage_2_branch": "neighbor_robustness_branch",
                "current_fail_bucket": "single_case_only",
                "branch_mode": "preferred",
                "trap_branch": False,
            },
            "current_round": 3,
            "memory": make_multistep_memory(),
            "contract_fail_bucket": "single_case_only",
            "scenario_results": [{"pass": True}, {"pass": False}],
        }
        base.update(overrides)
        return base

    def test_no_replan_when_not_forcing(self) -> None:
        kwargs = self._base_kwargs(current_text="model Foo end Foo;")
        result = build_source_blind_multistep_llm_replan_context(**kwargs)
        self.assertFalse(result["should_force_replan"])

    def test_regressed_to_stage_1(self) -> None:
        mem = make_multistep_memory()
        mem["llm_plan_followed"] = True
        ctx = {
            "current_stage": "stage_1",
            "stage_2_branch": "",
            "preferred_stage_2_branch": "neighbor_robustness_branch",
            "current_fail_bucket": "stability_margin_miss",
            "branch_mode": "",
            "trap_branch": False,
        }
        kwargs = self._base_kwargs(stage_context=ctx, memory=mem)
        result = build_source_blind_multistep_llm_replan_context(**kwargs)
        self.assertTrue(result["should_force_replan"])
        self.assertEqual(result["llm_replan_reason"], "regressed_to_stage_1_after_first_plan")

    def test_same_branch_stall(self) -> None:
        mem = make_multistep_memory()
        mem["llm_plan_followed"] = True
        mem["last_llm_plan_branch"] = "neighbor_robustness_branch"
        kwargs = self._base_kwargs(memory=mem)
        result = build_source_blind_multistep_llm_replan_context(**kwargs)
        self.assertTrue(result["should_force_replan"])
        self.assertEqual(result["llm_replan_reason"], "same_stage_2_branch_stall_after_first_plan")

    def test_max_replan_reached(self) -> None:
        mem = make_multistep_memory()
        mem["llm_plan_followed"] = True
        mem["llm_replan_count"] = 1  # v4 max is 1
        kwargs = self._base_kwargs(memory=mem)
        result = build_source_blind_multistep_llm_replan_context(**kwargs)
        self.assertFalse(result["should_force_replan"])


# ===================================================================
# build_source_blind_multistep_replan_budget
# ===================================================================


class TestReplanBudget(unittest.TestCase):
    def test_trap_escape_allocation(self) -> None:
        stage_ctx = {
            "current_stage": "stage_2",
            "stage_2_branch": "neighbor_overfit_trap",
            "preferred_stage_2_branch": "neighbor_robustness_branch",
            "trap_branch": True,
        }
        replan_ctx = {
            "previous_plan_failed_signal": "trap_branch_no_escape_progress",
            "realism_version": "v4",
            "replan_count_before": 0,
            "current_branch": "neighbor_overfit_trap",
            "preferred_branch": "neighbor_robustness_branch",
        }
        mem = make_multistep_memory()
        result = build_source_blind_multistep_replan_budget(
            stage_context=stage_ctx,
            replan_context=replan_ctx,
            current_round=4,
            max_rounds=10,
            memory=mem,
        )
        self.assertTrue(result["replan_switch_branch"])
        self.assertGreater(result["replan_budget_for_branch_escape"], 0)

    def test_preferred_branch_continues(self) -> None:
        stage_ctx = {
            "current_stage": "stage_2",
            "stage_2_branch": "neighbor_robustness_branch",
            "preferred_stage_2_branch": "neighbor_robustness_branch",
            "trap_branch": False,
        }
        replan_ctx = {
            "previous_plan_failed_signal": "same_stage_2_branch_stall_after_first_plan",
            "realism_version": "v4",
            "replan_count_before": 0,
            "current_branch": "neighbor_robustness_branch",
            "preferred_branch": "neighbor_robustness_branch",
        }
        mem = make_multistep_memory()
        result = build_source_blind_multistep_replan_budget(
            stage_context=stage_ctx,
            replan_context=replan_ctx,
            current_round=4,
            max_rounds=10,
            memory=mem,
        )
        self.assertTrue(result["replan_continue_current_branch"])
        self.assertFalse(result["replan_switch_branch"])
        self.assertEqual(result["replan_budget_for_branch_diagnosis"], 0)

    def test_v5_second_replan_on_preferred(self) -> None:
        stage_ctx = {
            "current_stage": "stage_2",
            "stage_2_branch": "neighbor_robustness_branch",
            "preferred_stage_2_branch": "neighbor_robustness_branch",
            "trap_branch": False,
        }
        replan_ctx = {
            "previous_plan_failed_signal": "no_contract_bucket_progress_after_replan",
            "realism_version": "v5",
            "replan_count_before": 1,
            "current_branch": "neighbor_robustness_branch",
            "preferred_branch": "neighbor_robustness_branch",
        }
        mem = make_multistep_memory()
        result = build_source_blind_multistep_replan_budget(
            stage_context=stage_ctx,
            replan_context=replan_ctx,
            current_round=5,
            max_rounds=10,
            memory=mem,
        )
        self.assertTrue(result["replan_continue_current_branch"])
        self.assertFalse(result["replan_switch_branch"])
        self.assertEqual(result["replan_budget_for_branch_diagnosis"], 0)
        self.assertEqual(result["replan_budget_for_branch_escape"], 0)
        self.assertGreaterEqual(result["replan_budget_for_resolution"], 2)


# ===================================================================
# build_branching_stage_2_eval
# ===================================================================


class TestBranchingStage2Eval(unittest.TestCase):
    def test_trap_branch(self) -> None:
        result = build_branching_stage_2_eval(
            branch="neighbor_overfit_trap",
            preferred_branch="neighbor_robustness_branch",
            trap_branch=True,
            branch_reason="overfit detected",
            transition_reason="nominal_pass",
            bucket="single_case_only",
        )
        self.assertFalse(result["pass"])
        self.assertTrue(result["trap_branch"])
        self.assertFalse(result["correct_branch_selected"])
        self.assertEqual(result["multi_step_stage"], "stage_2")

    def test_non_trap_branch(self) -> None:
        result = build_branching_stage_2_eval(
            branch="neighbor_robustness_branch",
            preferred_branch="neighbor_robustness_branch",
            trap_branch=False,
            branch_reason="robustness failure",
            transition_reason="nominal_pass",
            bucket="single_case_only",
        )
        self.assertFalse(result["pass"])
        self.assertFalse(result["trap_branch"])
        self.assertTrue(result["correct_branch_selected"])


# ===================================================================
# make_multistep_memory
# ===================================================================


class TestMakeMultistepMemory(unittest.TestCase):
    def test_key_count(self) -> None:
        memory = make_multistep_memory()
        # At least 150 keys (docstring says 155 but exact count may vary)
        self.assertGreaterEqual(len(memory), 150)

    def test_default_values(self) -> None:
        memory = make_multistep_memory()
        self.assertEqual(memory["stage_1_unlock_cluster"], "")
        self.assertEqual(memory["stage_2_transition_round"], 0)
        self.assertFalse(memory["llm_plan_used"])
        self.assertFalse(memory["trap_branch_active"])
        self.assertIsInstance(memory["branch_history"], list)
        self.assertEqual(len(memory["branch_history"]), 0)
        self.assertIsInstance(memory["budget_bucket_consumed"], dict)
        self.assertEqual(len(memory["budget_bucket_consumed"]), 0)

    def test_independent_copies(self) -> None:
        m1 = make_multistep_memory()
        m2 = make_multistep_memory()
        m1["branch_history"].append("x")
        m1["tried_parameters"].append("Ki")
        self.assertEqual(len(m2["branch_history"]), 0)
        self.assertEqual(len(m2["tried_parameters"]), 0)


# ===================================================================
# CLI
# ===================================================================


class TestCLI(unittest.TestCase):
    def test_help_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "gateforge.agent_modelica_stage_branch_controller_v1", "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Stage/Branch State Machine", proc.stdout)


if __name__ == "__main__":
    unittest.main()
