from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_13_2_closeout import build_v132_closeout
from gateforge.agent_modelica_v0_13_2_handoff_integrity import build_v132_handoff_integrity
from gateforge.agent_modelica_v0_13_2_remaining_capability_intervention_scope_assessment import (
    build_v132_remaining_capability_intervention_scope_assessment,
)
from gateforge.agent_modelica_v0_13_2_stronger_capability_intervention_scope_summary import (
    build_v132_stronger_capability_intervention_scope_summary,
)


def _write_v131_closeout(path: Path, *, effect_class: str = "non_material", bad_handoff: bool = False) -> None:
    if bad_handoff:
        conclusion = {
            "version_decision": "v0_13_1_first_capability_intervention_pack_mainline_material",
            "intervention_effect_class": "material",
            "pre_intervention_run_reference": "artifacts/pre.json",
            "post_intervention_run_reference": "artifacts/post.json",
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_13_2_handoff_mode": "characterize_first_capability_effect_profile",
        }
    else:
        version_decision = (
            "v0_13_1_first_capability_intervention_pack_side_evidence_only"
            if effect_class == "side_evidence_only"
            else "v0_13_1_first_capability_intervention_pack_non_material"
        )
        conclusion = {
            "version_decision": version_decision,
            "intervention_effect_class": effect_class,
            "pre_intervention_run_reference": "artifacts/pre.json",
            "post_intervention_run_reference": "artifacts/post.json",
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_13_2_handoff_mode": "determine_whether_stronger_bounded_capability_intervention_is_in_scope",
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"conclusion": conclusion}), encoding="utf-8")


def _write_v130_governance_pack(path: Path) -> None:
    payload = {
        "capability_intervention_admission": {
            "admitted_rows": [
                {"intervention_id": "bounded_execution_strategy_upgrade_v1"},
                {"intervention_id": "bounded_replan_search_control_upgrade_v1"},
                {"intervention_id": "bounded_failure_diagnosis_upgrade_v1"},
            ]
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v115_closeout(path: Path, *, dominant_gap: str = "residual_core_capability_gap") -> None:
    payload = {
        "conclusion": {
            "formal_adjudication_label": "product_gap_partial_but_interpretable",
            "dominant_gap_family_readout": dominant_gap,
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV132CapabilityInterventionScopeAdjudicationFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path_non_material(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v131 = root / "v131.json"
            _write_v131_closeout(v131, effect_class="non_material")
            payload = build_v132_handoff_integrity(v131_closeout_path=str(v131), out_dir=str(root / "integrity"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_pass_path_side_evidence_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v131 = root / "v131.json"
            _write_v131_closeout(v131, effect_class="side_evidence_only")
            payload = build_v132_handoff_integrity(v131_closeout_path=str(v131), out_dir=str(root / "integrity"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v131 = root / "v131_bad.json"
            _write_v131_closeout(v131, bad_handoff=True)
            payload = build_v132_handoff_integrity(v131_closeout_path=str(v131), out_dir=str(root / "integrity"))
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_justified_path_with_concrete_stronger_bounded_intervention(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v131 = root / "v131.json"
            v130 = root / "v130.json"
            v115 = root / "v115.json"
            _write_v131_closeout(v131)
            _write_v130_governance_pack(v130)
            _write_v115_closeout(v115)
            assessment = build_v132_remaining_capability_intervention_scope_assessment(
                v131_closeout_path=str(v131),
                v130_governance_pack_path=str(v130),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
                scope_relevant_uncertainty_remains=True,
                uncertainty_is_bounded_step_addressable=True,
                expected_information_gain="non_marginal",
                candidate_next_intervention_shape="stronger_l2_planner_strategy_upgrade",
                named_blocker_if_not_in_scope="",
            )
            self.assertEqual(
                assessment["remaining_capability_intervention_scope_object"]["remaining_scope_status"],
                "stronger_bounded_capability_intervention_still_in_scope",
            )
            summary = build_v132_stronger_capability_intervention_scope_summary(
                remaining_capability_intervention_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
                candidate_intervention_id="stronger_execution_strategy_upgrade_v2",
                candidate_intervention_family="capability_level_execution_strategy_improvement",
                candidate_intervention_shape="stronger_l2_planner_strategy_upgrade",
                target_gap_family="residual_core_capability_gap",
                target_failure_mode="underpowered_multistep_execution_strategy_after_first_pack",
                why_stronger_than_first_pack="targets a deeper L2 execution-policy surface than the first pack rather than re-running the same prompt-surface hint",
                why_still_bounded="bounded to one additional execution-policy change surface with same-source comparison still possible",
                expected_effect_type="mainline_workflow_improvement",
                same_source_comparison_still_possible=True,
                out_of_scope_trigger_table={
                    "broad_model_family_replacement_required": False,
                    "task_base_widening_required": False,
                    "same_source_comparison_break_required": False,
                    "per_intervention_ablation_required_before_next_step": False,
                    "admitted_intervention_families_already_exhausted": False,
                },
            )
            self.assertEqual(summary["stronger_intervention_scope_status"], "justified")

    def test_not_in_scope_on_default_non_material_posture(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v131 = root / "v131.json"
            v130 = root / "v130.json"
            v115 = root / "v115.json"
            _write_v131_closeout(v131)
            _write_v130_governance_pack(v130)
            _write_v115_closeout(v115)
            assessment = build_v132_remaining_capability_intervention_scope_assessment(
                v131_closeout_path=str(v131),
                v130_governance_pack_path=str(v130),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
            )
            self.assertFalse(
                assessment["remaining_capability_intervention_scope_object"]["scope_relevant_uncertainty_remains"]
            )
            summary = build_v132_stronger_capability_intervention_scope_summary(
                remaining_capability_intervention_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            self.assertEqual(summary["stronger_intervention_scope_status"], "not_in_scope")

    def test_not_in_scope_when_scope_relevant_uncertainty_false(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v131 = root / "v131.json"
            v130 = root / "v130.json"
            v115 = root / "v115.json"
            _write_v131_closeout(v131, effect_class="side_evidence_only")
            _write_v130_governance_pack(v130)
            _write_v115_closeout(v115)
            assessment = build_v132_remaining_capability_intervention_scope_assessment(
                v131_closeout_path=str(v131),
                v130_governance_pack_path=str(v130),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
                scope_relevant_uncertainty_remains=False,
                expected_information_gain="non_marginal",
                candidate_next_intervention_shape="stronger_search_budget_and_replan_control",
            )
            scope_obj = assessment["remaining_capability_intervention_scope_object"]
            self.assertEqual(scope_obj["expected_information_gain"], "marginal")
            self.assertEqual(scope_obj["candidate_next_intervention_shape"], "none")
            summary = build_v132_stronger_capability_intervention_scope_summary(
                remaining_capability_intervention_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            self.assertEqual(summary["stronger_intervention_scope_status"], "not_in_scope")

    def test_invalid_when_candidate_claimed_but_same_source_false(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v131 = root / "v131.json"
            v130 = root / "v130.json"
            v115 = root / "v115.json"
            _write_v131_closeout(v131)
            _write_v130_governance_pack(v130)
            _write_v115_closeout(v115)
            build_v132_remaining_capability_intervention_scope_assessment(
                v131_closeout_path=str(v131),
                v130_governance_pack_path=str(v130),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
                scope_relevant_uncertainty_remains=True,
                uncertainty_is_bounded_step_addressable=True,
                expected_information_gain="non_marginal",
                candidate_next_intervention_shape="stronger_l3_l4_failure_diagnosis_chain",
            )
            summary = build_v132_stronger_capability_intervention_scope_summary(
                remaining_capability_intervention_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
                candidate_intervention_id="stronger_failure_diagnosis_upgrade_v2",
                candidate_intervention_family="failure_state_diagnosis_improvement",
                candidate_intervention_shape="stronger_l3_l4_failure_diagnosis_chain",
                target_gap_family="residual_core_capability_gap",
                target_failure_mode="underpowered_failure_diagnosis_after_first_pack",
                why_stronger_than_first_pack="adds deeper diagnosis chain branching beyond the first pack surface",
                why_still_bounded="remains inside one diagnosis-chain change surface",
                expected_effect_type="mainline_workflow_improvement",
                same_source_comparison_still_possible=False,
            )
            self.assertEqual(summary["stronger_intervention_scope_status"], "invalid")

    def test_closeout_routes_on_not_in_scope_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v131 = root / "v131.json"
            v130 = root / "v130.json"
            v115 = root / "v115.json"
            _write_v131_closeout(v131)
            _write_v130_governance_pack(v130)
            _write_v115_closeout(v115)
            build_v132_handoff_integrity(v131_closeout_path=str(v131), out_dir=str(root / "integrity"))
            build_v132_remaining_capability_intervention_scope_assessment(
                v131_closeout_path=str(v131),
                v130_governance_pack_path=str(v130),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
            )
            build_v132_stronger_capability_intervention_scope_summary(
                remaining_capability_intervention_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            payload = build_v132_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_capability_intervention_scope_assessment_path=str(root / "assessment" / "summary.json"),
                stronger_capability_intervention_scope_summary_path=str(root / "summary" / "summary.json"),
                v131_closeout_path=str(v131),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_13_2_stronger_bounded_capability_intervention_not_in_scope",
            )
            self.assertEqual(payload["conclusion"]["v0_13_3_handoff_mode"], "prepare_v0_13_phase_synthesis")


if __name__ == "__main__":
    unittest.main()
