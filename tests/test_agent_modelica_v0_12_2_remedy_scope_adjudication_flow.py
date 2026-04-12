from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_12_2_closeout import build_v122_closeout
from gateforge.agent_modelica_v0_12_2_handoff_integrity import build_v122_handoff_integrity
from gateforge.agent_modelica_v0_12_2_remaining_remedy_scope_assessment import (
    build_v122_remaining_remedy_scope_assessment,
)
from gateforge.agent_modelica_v0_12_2_stronger_remedy_scope_summary import (
    build_v122_stronger_remedy_scope_summary,
)


def _write_v121_closeout(path: Path, *, bad_handoff: bool = False) -> None:
    if bad_handoff:
        conclusion = {
            "version_decision": "v0_12_1_first_remedy_pack_side_evidence_only",
            "pack_level_effect": "side_evidence_only",
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_12_2_handoff_mode": "determine_whether_stronger_remedy_is_in_scope",
        }
    else:
        conclusion = {
            "version_decision": "v0_12_1_first_remedy_pack_non_material",
            "pack_level_effect": "non_material",
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_12_2_handoff_mode": "determine_whether_stronger_remedy_is_in_scope",
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"conclusion": conclusion}), encoding="utf-8")


class AgentModelicaV122RemedyScopeAdjudicationFlowTests(unittest.TestCase):

    # ---- Test 1: handoff-integrity pass path --------------------------------

    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v121 = root / "v121.json"
            _write_v121_closeout(v121)
            payload = build_v122_handoff_integrity(
                v121_closeout_path=str(v121),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    # ---- Test 2: handoff-integrity invalid path -----------------------------

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v121 = root / "v121_bad.json"
            _write_v121_closeout(v121, bad_handoff=True)
            payload = build_v122_handoff_integrity(
                v121_closeout_path=str(v121),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    # ---- Test 3: justified path with concrete stronger bounded remedy -------

    def test_justified_path_with_concrete_stronger_bounded_remedy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v121 = root / "v121.json"
            _write_v121_closeout(v121)
            scope_assessment = build_v122_remaining_remedy_scope_assessment(
                v121_closeout_path=str(v121),
                out_dir=str(root / "scope_assessment"),
                scope_relevant_uncertainty_remains=True,
                uncertainty_is_bounded_step_addressable=True,
                expected_information_gain="non_marginal",
                candidate_next_remedy_shape="stronger_context_contract_hardening",
                named_blocker_if_not_in_scope="",
            )
            self.assertEqual(
                scope_assessment["remaining_remedy_scope_object"]["remaining_scope_status"],
                "stronger_bounded_remedy_still_in_scope",
            )
            scope_summary = build_v122_stronger_remedy_scope_summary(
                remaining_remedy_scope_assessment_path=str(root / "scope_assessment" / "summary.json"),
                out_dir=str(root / "scope_summary"),
                candidate_remedy_id="stronger_workflow_goal_reanchoring_v2",
                candidate_remedy_family="context_contract_hardening",
                candidate_remedy_shape="stronger_context_contract_hardening",
                target_gap_family="context_discipline_gap",
                target_failure_mode="persistent_goal_drift_across_multi_round_omc_calls",
                why_stronger_than_first_pack=(
                    "injects goal reanchoring at finer granularity per omc sub-call rather than "
                    "once per planner round; targets the specific context-window truncation mode "
                    "observed to persist after first-pack hardening"
                ),
                why_still_bounded="single instrumentation point change with same-source comparison possible",
                expected_effect_type="goal_alignment_improvement_on_long_horizon_cases",
                same_source_comparison_still_possible=True,
                out_of_scope_trigger_table={
                    "broad_capability_rewrite_required": False,
                    "task_base_widening_required": False,
                    "same_source_comparison_break_required": False,
                    "per_remedy_ablation_required_before_next_step": False,
                    "unbounded_prompt_architecture_change_required": False,
                },
            )
            self.assertEqual(scope_summary["stronger_remedy_scope_status"], "justified")
            self.assertEqual(
                scope_summary["stronger_remedy_candidate_object"]["candidate_remedy_id"],
                "stronger_workflow_goal_reanchoring_v2",
            )

    # ---- Test 4: not-in-scope on real non_material posture ------------------

    def test_not_in_scope_on_real_non_material_posture(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v121 = root / "v121.json"
            _write_v121_closeout(v121)
            # Use all defaults: non_material + residual_core_capability_gap → not_in_scope
            scope_assessment = build_v122_remaining_remedy_scope_assessment(
                v121_closeout_path=str(v121),
                out_dir=str(root / "scope_assessment"),
            )
            self.assertFalse(scope_assessment["remaining_remedy_scope_object"]["scope_relevant_uncertainty_remains"])
            self.assertEqual(scope_assessment["remaining_remedy_scope_object"]["expected_information_gain"], "marginal")
            scope_summary = build_v122_stronger_remedy_scope_summary(
                remaining_remedy_scope_assessment_path=str(root / "scope_assessment" / "summary.json"),
                out_dir=str(root / "scope_summary"),
            )
            self.assertEqual(scope_summary["stronger_remedy_scope_status"], "not_in_scope")

    # ---- Test 5: not-in-scope when uncertainty is not phase-relevant --------

    def test_not_in_scope_when_uncertainty_not_phase_relevant(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v121 = root / "v121.json"
            _write_v121_closeout(v121)
            # scope_relevant_uncertainty_remains = False forces marginal gain and none shape
            scope_assessment = build_v122_remaining_remedy_scope_assessment(
                v121_closeout_path=str(v121),
                out_dir=str(root / "scope_assessment"),
                scope_relevant_uncertainty_remains=False,
                expected_information_gain="non_marginal",  # hard rule overrides this to marginal
                candidate_next_remedy_shape="stronger_protocol_shell_hardening",  # hard rule collapses to none
            )
            scope_obj = scope_assessment["remaining_remedy_scope_object"]
            self.assertEqual(scope_obj["expected_information_gain"], "marginal")
            self.assertEqual(scope_obj["candidate_next_remedy_shape"], "none")
            scope_summary = build_v122_stronger_remedy_scope_summary(
                remaining_remedy_scope_assessment_path=str(root / "scope_assessment" / "summary.json"),
                out_dir=str(root / "scope_summary"),
            )
            self.assertEqual(scope_summary["stronger_remedy_scope_status"], "not_in_scope")

    # ---- Test 6: invalid when candidate claimed but same_source = false -----

    def test_invalid_when_candidate_claimed_but_same_source_comparison_false(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v121 = root / "v121.json"
            _write_v121_closeout(v121)
            build_v122_remaining_remedy_scope_assessment(
                v121_closeout_path=str(v121),
                out_dir=str(root / "scope_assessment"),
                scope_relevant_uncertainty_remains=True,
                uncertainty_is_bounded_step_addressable=True,
                expected_information_gain="non_marginal",
                candidate_next_remedy_shape="stronger_error_visibility_hardening",
            )
            scope_summary = build_v122_stronger_remedy_scope_summary(
                remaining_remedy_scope_assessment_path=str(root / "scope_assessment" / "summary.json"),
                out_dir=str(root / "scope_summary"),
                candidate_remedy_id="stronger_omc_error_pipe_v2",
                candidate_remedy_family="error_propagation_and_visibility_hardening",
                candidate_remedy_shape="stronger_error_visibility_hardening",
                target_gap_family="omc_error_visibility_gap",
                target_failure_mode="silent_error_swallowing_in_nested_omc_calls",
                why_stronger_than_first_pack="pipes full nested error trace not just top-level",
                why_still_bounded="instrumentation-only change to error propagation path",
                expected_effect_type="error_visibility_improvement",
                same_source_comparison_still_possible=False,  # triggers invalid
            )
            self.assertEqual(scope_summary["stronger_remedy_scope_status"], "invalid")
            self.assertIn("same_source", scope_summary["invalid_reason"])

    # ---- Test 7: invalid when shape != none but no candidate id -------------

    def test_invalid_when_shape_non_none_but_no_concrete_remedy_id(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v121 = root / "v121.json"
            _write_v121_closeout(v121)
            build_v122_remaining_remedy_scope_assessment(
                v121_closeout_path=str(v121),
                out_dir=str(root / "scope_assessment"),
                scope_relevant_uncertainty_remains=True,
                uncertainty_is_bounded_step_addressable=True,
                expected_information_gain="non_marginal",
                candidate_next_remedy_shape="stronger_protocol_shell_hardening",
            )
            scope_summary = build_v122_stronger_remedy_scope_summary(
                remaining_remedy_scope_assessment_path=str(root / "scope_assessment" / "summary.json"),
                out_dir=str(root / "scope_summary"),
                candidate_remedy_id="",  # empty → invalid
                candidate_remedy_shape="stronger_protocol_shell_hardening",
                same_source_comparison_still_possible=True,
            )
            self.assertEqual(scope_summary["stronger_remedy_scope_status"], "invalid")
            self.assertIn("remedy_id", scope_summary["invalid_reason"])

    # ---- Test 8: closeout routing on justified path -------------------------

    def test_closeout_routes_to_stronger_bounded_remedy_justified(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v121 = root / "v121.json"
            _write_v121_closeout(v121)
            build_v122_handoff_integrity(
                v121_closeout_path=str(v121),
                out_dir=str(root / "integrity"),
            )
            build_v122_remaining_remedy_scope_assessment(
                v121_closeout_path=str(v121),
                out_dir=str(root / "scope_assessment"),
                scope_relevant_uncertainty_remains=True,
                uncertainty_is_bounded_step_addressable=True,
                expected_information_gain="non_marginal",
                candidate_next_remedy_shape="stronger_context_contract_hardening",
            )
            build_v122_stronger_remedy_scope_summary(
                remaining_remedy_scope_assessment_path=str(root / "scope_assessment" / "summary.json"),
                out_dir=str(root / "scope_summary"),
                candidate_remedy_id="stronger_workflow_goal_reanchoring_v2",
                candidate_remedy_family="context_contract_hardening",
                candidate_remedy_shape="stronger_context_contract_hardening",
                target_gap_family="context_discipline_gap",
                target_failure_mode="persistent_goal_drift_across_multi_round_omc_calls",
                why_stronger_than_first_pack="per-omc-call reanchoring instead of per-planner-round",
                why_still_bounded="single instrumentation point with same-source comparison possible",
                expected_effect_type="goal_alignment_improvement_on_long_horizon_cases",
                same_source_comparison_still_possible=True,
                out_of_scope_trigger_table={
                    "broad_capability_rewrite_required": False,
                    "task_base_widening_required": False,
                    "same_source_comparison_break_required": False,
                    "per_remedy_ablation_required_before_next_step": False,
                    "unbounded_prompt_architecture_change_required": False,
                },
            )
            payload = build_v122_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_remedy_scope_assessment_path=str(root / "scope_assessment" / "summary.json"),
                stronger_remedy_scope_summary_path=str(root / "scope_summary" / "summary.json"),
                v121_closeout_path=str(v121),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_12_2_stronger_bounded_remedy_justified",
            )
            self.assertEqual(
                payload["conclusion"]["v0_12_3_handoff_mode"],
                "execute_stronger_bounded_operational_remedy",
            )


if __name__ == "__main__":
    unittest.main()
