from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_15_0_closeout import build_v150_closeout
from gateforge.agent_modelica_v0_15_0_governance_pack import build_v150_governance_pack
from gateforge.agent_modelica_v0_15_0_handoff_integrity import build_v150_handoff_integrity


def _write_closeout(path: Path, conclusion: dict, **extra: dict) -> None:
    payload = {"conclusion": conclusion}
    payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v112": root / "v112" / "summary.json",
        "v141": root / "v141" / "summary.json",
        "v142": root / "v142" / "summary.json",
        "v143": root / "v143" / "summary.json",
    }
    _write_closeout(
        paths["v112"],
        {
            "version_decision": "v0_11_2_first_product_gap_substrate_ready",
            "v0_11_3_handoff_mode": "characterize_first_product_gap_profile",
        },
        product_gap_substrate_builder={
            "carried_baseline_source": "v0_10_3_frozen_12_case_real_origin_substrate",
            "product_gap_candidate_table": [
                {
                    "task_id": f"task_{i}",
                    "source_id": f"source_{i}",
                    "family_id": f"family_{i}",
                    "workflow_task_template_id": f"template_{i}",
                    "product_gap_scaffold_version": "gateforge_live_executor_v1_scaffold",
                    "product_gap_protocol_contract_version": "gateforge_live_executor_v1_contract",
                }
                for i in range(12)
            ],
        },
    )
    _write_closeout(
        paths["v141"],
        {
            "version_decision": "v0_14_1_first_broader_change_pack_non_material",
            "broader_change_effect_class": "non_material",
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_14_2_handoff_mode": "determine_whether_stronger_broader_change_is_in_scope",
        },
    )
    _write_closeout(
        paths["v142"],
        {
            "version_decision": "v0_14_2_stronger_broader_change_not_in_scope",
            "stronger_broader_change_scope_status": "not_in_scope",
            "expected_information_gain": "marginal",
            "named_blocker_if_not_in_scope": "admitted_broader_change_set_covers_available_scope_and_residual_gap_requires_broader_than_governed_change",
            "v0_14_3_handoff_mode": "prepare_v0_14_phase_synthesis",
        },
    )
    _write_closeout(
        paths["v143"],
        {
            "version_decision": "v0_14_phase_nearly_complete_with_explicit_caveat",
            "phase_stop_condition_status": "nearly_complete_with_caveat",
            "explicit_caveat_present": True,
            "explicit_caveat_label": "bounded_capability_interventions_and_governed_broader_changes_did_not_materially_rewrite_the_carried_product_gap_picture_and_stronger_governed_broader_escalation_is_not_in_scope",
            "next_primary_phase_question": "post_broader_change_exhaustion_even_broader_change_evaluation",
            "do_not_continue_v0_14_same_broader_change_refinement_by_default": True,
        },
    )
    return paths


class AgentModelicaV150EvenBroaderChangeGovernanceFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v150_handoff_integrity(
                v143_closeout_path=str(paths["v143"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v143"],
                {
                    "version_decision": "v0_14_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "bounded_capability_interventions_and_governed_broader_changes_did_not_materially_rewrite_the_carried_product_gap_picture_and_stronger_governed_broader_escalation_is_not_in_scope",
                    "next_primary_phase_question": "post_broader_change_exhaustion_even_broader_change_evaluation",
                    "do_not_continue_v0_14_same_broader_change_refinement_by_default": False,
                },
            )
            payload = build_v150_handoff_integrity(
                v143_closeout_path=str(paths["v143"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_baseline_anchor_pass_on_carried_v143_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v150_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                v143_closeout_path=str(paths["v143"]),
                out_dir=str(root / "governance"),
            )
            self.assertTrue(payload["even_broader_change_baseline_anchor"]["baseline_anchor_pass"])
            self.assertEqual(payload["even_broader_change_baseline_anchor"]["carried_phase_closeout_version"], "v0_14_3")

    def test_family_separation_ready_path_when_overlap_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v150_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                v143_closeout_path=str(paths["v143"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["even_broader_change_family_separation_rule"]["family_separation_status"], "ready")
            self.assertEqual(
                payload["even_broader_change_family_separation_rule"]["strict_separation_table"][0]["family_name"],
                "cross_layer_execution_diagnosis_restructuring",
            )

    def test_rejects_broad_unconstrained_rewrite_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v150_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                v143_closeout_path=str(paths["v143"]),
                out_dir=str(root / "governance"),
            )
            self.assertIn(
                {
                    "candidate_id": "broad_unconstrained_rewrite_candidate",
                    "rejection_reason": "broad_unconstrained_rewrite_out_of_scope",
                },
                payload["even_broader_change_admission"]["rejection_reason_table"],
            )

    def test_governance_partial_when_baseline_continuity_is_broken(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            broken_rows = [
                {
                    "task_id": f"task_{i}",
                    "source_id": f"source_{i}",
                    "family_id": f"family_{i}",
                    "workflow_task_template_id": f"template_{i}",
                    "product_gap_scaffold_version": "gateforge_live_executor_v1_scaffold",
                    "product_gap_protocol_contract_version": "" if i == 0 else "gateforge_live_executor_v1_contract",
                }
                for i in range(12)
            ]
            _write_closeout(
                paths["v112"],
                {
                    "version_decision": "v0_11_2_first_product_gap_substrate_ready",
                },
                product_gap_substrate_builder={
                    "carried_baseline_source": "v0_10_3_frozen_12_case_real_origin_substrate",
                    "product_gap_candidate_table": broken_rows,
                },
            )
            payload = build_v150_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                v143_closeout_path=str(paths["v143"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["baseline_continuity_check"]["baseline_continuity_check_status"], "broken")
            self.assertEqual(payload["even_broader_change_governance_status"], "governance_partial")
            self.assertFalse(payload["governance_ready_for_runtime_execution"])

    def test_governance_partial_when_execution_arc_viability_is_not_justified(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v150_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                v143_closeout_path=str(paths["v143"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["execution_arc_viability"]["execution_arc_viability_status"], "not_justified")
            self.assertEqual(payload["even_broader_change_governance_status"], "governance_partial")

    def test_closeout_routes_to_governance_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            candidate_registry = {
                "candidate_rows": [
                    {
                        "candidate_id": "cross_layer_execution_diagnosis_restructuring_v1",
                        "candidate_family": "cross_layer_execution_diagnosis_restructuring",
                        "target_gap_family": "residual_core_capability_gap",
                        "target_failure_mode": "single_surface_broader_change_pack_still_fails_to_shift_mainline_behavior",
                        "expected_effect_type": "mainline_workflow_improvement",
                        "even_broader_change_surface": "coordinated_L2_L3_L4_execution_and_diagnosis_restructuring",
                        "why_broader_than_v0_14_governed_pack": "Cross-layer restructuring is materially stronger than the v0.14 governed pack.",
                        "why_still_comparable_on_carried_baseline": "Same carried 12-case baseline, same executor shell, same Docker/runtime stack.",
                        "admission_status": "admitted",
                    }
                ]
            }
            viability_object = {
                "execution_arc_viability_status": "justified",
                "scope_relevant_uncertainty_remains": True,
                "named_viability_question": "Can cross-layer restructuring produce a different failure-mode distribution on the carried same-source 12-case baseline?",
                "expected_information_gain": "non_marginal",
                "concrete_first_pack_available": True,
                "same_source_comparison_still_possible": True,
                "named_reason_if_not_justified": "",
            }
            build_v150_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                v143_closeout_path=str(paths["v143"]),
                candidate_registry=candidate_registry,
                execution_arc_viability_object=viability_object,
                out_dir=str(root / "governance"),
            )
            payload = build_v150_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                v143_closeout_path=str(paths["v143"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_15_0_even_broader_change_governance_ready")
            self.assertEqual(payload["conclusion"]["v0_15_1_handoff_mode"], "execute_first_even_broader_change_pack")

    def test_closeout_routes_to_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v143"],
                {
                    "version_decision": "v0_14_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "bounded_capability_interventions_and_governed_broader_changes_did_not_materially_rewrite_the_carried_product_gap_picture_and_stronger_governed_broader_escalation_is_not_in_scope",
                    "next_primary_phase_question": "post_broader_change_exhaustion_even_broader_change_evaluation",
                    "do_not_continue_v0_14_same_broader_change_refinement_by_default": False,
                },
            )
            payload = build_v150_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                v143_closeout_path=str(paths["v143"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_15_0_handoff_phase_inputs_invalid")
            self.assertEqual(payload["conclusion"]["v0_15_1_handoff_mode"], "rebuild_v0_15_0_phase_inputs_first")


if __name__ == "__main__":
    unittest.main()
