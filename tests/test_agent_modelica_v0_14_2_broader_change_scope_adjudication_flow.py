from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_14_2_closeout import build_v142_closeout
from gateforge.agent_modelica_v0_14_2_handoff_integrity import build_v142_handoff_integrity
from gateforge.agent_modelica_v0_14_2_remaining_broader_change_scope_assessment import (
    build_v142_remaining_broader_change_scope_assessment,
)
from gateforge.agent_modelica_v0_14_2_stronger_broader_change_scope_summary import (
    build_v142_stronger_broader_change_scope_summary,
)


def _write_v141_closeout(path: Path, *, effect_class: str = "non_material", bad_handoff: bool = False) -> None:
    if bad_handoff:
        conclusion = {
            "version_decision": "v0_14_1_first_broader_change_pack_mainline_material",
            "broader_change_effect_class": "mainline_material",
            "pre_intervention_run_reference": "artifacts/pre.json",
            "post_intervention_run_reference": "artifacts/post.json",
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_14_2_handoff_mode": "characterize_first_broader_change_effect_profile",
        }
    else:
        version_decision = (
            "v0_14_1_first_broader_change_pack_side_evidence_only"
            if effect_class == "side_evidence_only"
            else "v0_14_1_first_broader_change_pack_non_material"
        )
        conclusion = {
            "version_decision": version_decision,
            "broader_change_effect_class": effect_class,
            "pre_intervention_run_reference": "artifacts/pre.json",
            "post_intervention_run_reference": "artifacts/post.json",
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_14_2_handoff_mode": "determine_whether_stronger_broader_change_is_in_scope",
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"conclusion": conclusion}), encoding="utf-8")


def _write_v140_governance_pack(path: Path) -> None:
    payload = {
        "broader_change_admission": {
            "admitted_rows": [
                {"candidate_id": "broader_L2_execution_policy_restructuring_v1"},
                {"candidate_id": "governed_llm_backbone_upgrade_v1"},
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


class AgentModelicaV142BroaderChangeScopeAdjudicationFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path_non_material(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v141 = root / "v141.json"
            _write_v141_closeout(v141, effect_class="non_material")
            payload = build_v142_handoff_integrity(v141_closeout_path=str(v141), out_dir=str(root / "integrity"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_pass_path_side_evidence_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v141 = root / "v141.json"
            _write_v141_closeout(v141, effect_class="side_evidence_only")
            payload = build_v142_handoff_integrity(v141_closeout_path=str(v141), out_dir=str(root / "integrity"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v141 = root / "v141_bad.json"
            _write_v141_closeout(v141, bad_handoff=True)
            payload = build_v142_handoff_integrity(v141_closeout_path=str(v141), out_dir=str(root / "integrity"))
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_justified_path_with_concrete_stronger_broader_change_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v141 = root / "v141.json"
            v140 = root / "v140.json"
            v115 = root / "v115.json"
            _write_v141_closeout(v141, effect_class="side_evidence_only")
            _write_v140_governance_pack(v140)
            _write_v115_closeout(v115)
            assessment = build_v142_remaining_broader_change_scope_assessment(
                v141_closeout_path=str(v141),
                v140_governance_pack_path=str(v140),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
                scope_relevant_uncertainty_remains=True,
                uncertainty_is_stronger_change_addressable=True,
                expected_information_gain="non_marginal",
                candidate_next_broader_change_shape="deeper_execution_policy_restructuring",
                named_blocker_if_not_in_scope="",
            )
            self.assertEqual(
                assessment["remaining_broader_change_scope_object"]["remaining_scope_status"],
                "stronger_broader_change_still_in_scope",
            )
            summary = build_v142_stronger_broader_change_scope_summary(
                remaining_broader_change_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
                candidate_broader_change_id="broader_execution_policy_restructuring_v2",
                candidate_broader_change_family="broader_execution_policy_restructuring",
                candidate_broader_change_shape="deeper_execution_policy_restructuring",
                target_gap_family="residual_core_capability_gap",
                target_failure_mode="underpowered_execution_policy_after_first_broader_pack",
                why_stronger_than_first_pack="targets a deeper execution-policy surface than the first broader pack rather than re-running the same admitted surface",
                why_still_governable="still bounded to one concrete execution-policy restructuring surface with same-source comparison preserved",
                expected_effect_type="mainline_workflow_improvement",
                same_source_comparison_still_possible=True,
                out_of_scope_trigger_table={
                    "task_base_widening_required": False,
                    "same_source_comparison_break_required": False,
                    "unconstrained_model_family_replacement_required": False,
                    "per_candidate_ablation_required_before_next_step": False,
                    "admitted_broader_change_set_already_exhausted": False,
                },
            )
            self.assertEqual(summary["stronger_broader_change_scope_status"], "justified")

    def test_not_in_scope_on_default_non_material_posture(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v141 = root / "v141.json"
            v140 = root / "v140.json"
            v115 = root / "v115.json"
            _write_v141_closeout(v141)
            _write_v140_governance_pack(v140)
            _write_v115_closeout(v115)
            assessment = build_v142_remaining_broader_change_scope_assessment(
                v141_closeout_path=str(v141),
                v140_governance_pack_path=str(v140),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
            )
            self.assertFalse(assessment["remaining_broader_change_scope_object"]["scope_relevant_uncertainty_remains"])
            summary = build_v142_stronger_broader_change_scope_summary(
                remaining_broader_change_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            self.assertEqual(summary["stronger_broader_change_scope_status"], "not_in_scope")

    def test_not_in_scope_when_scope_relevant_uncertainty_false(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v141 = root / "v141.json"
            v140 = root / "v140.json"
            v115 = root / "v115.json"
            _write_v141_closeout(v141, effect_class="side_evidence_only")
            _write_v140_governance_pack(v140)
            _write_v115_closeout(v115)
            assessment = build_v142_remaining_broader_change_scope_assessment(
                v141_closeout_path=str(v141),
                v140_governance_pack_path=str(v140),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
                scope_relevant_uncertainty_remains=False,
                expected_information_gain="non_marginal",
                candidate_next_broader_change_shape="stronger_governed_model_upgrade_variant",
            )
            scope_obj = assessment["remaining_broader_change_scope_object"]
            self.assertEqual(scope_obj["expected_information_gain"], "marginal")
            self.assertEqual(scope_obj["candidate_next_broader_change_shape"], "none")
            summary = build_v142_stronger_broader_change_scope_summary(
                remaining_broader_change_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            self.assertEqual(summary["stronger_broader_change_scope_status"], "not_in_scope")

    def test_invalid_when_candidate_claimed_but_same_source_false(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v141 = root / "v141.json"
            v140 = root / "v140.json"
            v115 = root / "v115.json"
            _write_v141_closeout(v141)
            _write_v140_governance_pack(v140)
            _write_v115_closeout(v115)
            build_v142_remaining_broader_change_scope_assessment(
                v141_closeout_path=str(v141),
                v140_governance_pack_path=str(v140),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
                scope_relevant_uncertainty_remains=True,
                uncertainty_is_stronger_change_addressable=True,
                expected_information_gain="non_marginal",
                candidate_next_broader_change_shape="stronger_governed_model_upgrade_variant",
            )
            summary = build_v142_stronger_broader_change_scope_summary(
                remaining_broader_change_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
                candidate_broader_change_id="governed_llm_backbone_upgrade_v2",
                candidate_broader_change_family="governed_model_upgrade_candidate",
                candidate_broader_change_shape="stronger_governed_model_upgrade_variant",
                target_gap_family="residual_core_capability_gap",
                target_failure_mode="residual_shortfall_after_first_broader_pack",
                why_stronger_than_first_pack="deepens the governed model-upgrade surface beyond the first admitted variant",
                why_still_governable="stays inside the governed backbone-upgrade scope",
                expected_effect_type="mainline_workflow_improvement",
                same_source_comparison_still_possible=False,
            )
            self.assertEqual(summary["stronger_broader_change_scope_status"], "invalid")

    def test_closeout_routes_on_not_in_scope_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v141 = root / "v141.json"
            v140 = root / "v140.json"
            v115 = root / "v115.json"
            _write_v141_closeout(v141)
            _write_v140_governance_pack(v140)
            _write_v115_closeout(v115)
            build_v142_handoff_integrity(v141_closeout_path=str(v141), out_dir=str(root / "integrity"))
            build_v142_remaining_broader_change_scope_assessment(
                v141_closeout_path=str(v141),
                v140_governance_pack_path=str(v140),
                v115_closeout_path=str(v115),
                out_dir=str(root / "assessment"),
            )
            build_v142_stronger_broader_change_scope_summary(
                remaining_broader_change_scope_assessment_path=str(root / "assessment" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            payload = build_v142_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_broader_change_scope_assessment_path=str(root / "assessment" / "summary.json"),
                stronger_broader_change_scope_summary_path=str(root / "summary" / "summary.json"),
                v141_closeout_path=str(v141),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_14_2_stronger_broader_change_not_in_scope",
            )
            self.assertEqual(payload["conclusion"]["v0_14_3_handoff_mode"], "prepare_v0_14_phase_synthesis")


if __name__ == "__main__":
    unittest.main()
