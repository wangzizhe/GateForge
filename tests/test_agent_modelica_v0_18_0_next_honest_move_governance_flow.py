from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_18_0_closeout import build_v180_closeout
from gateforge.agent_modelica_v0_18_0_governance_pack import build_v180_governance_pack
from gateforge.agent_modelica_v0_18_0_handoff_integrity import build_v180_handoff_integrity


def _write_closeout(path: Path, conclusion: dict, **extra: dict) -> None:
    payload = {"conclusion": conclusion}
    payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v112": root / "v112" / "summary.json",
        "v161": root / "v161" / "summary.json",
        "v170": root / "v170" / "summary.json",
        "v171": root / "v171" / "summary.json",
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
        paths["v161"],
        {
            "version_decision": "v0_16_phase_nearly_complete_with_explicit_caveat",
            "phase_stop_condition_status": "nearly_complete_with_caveat",
            "explicit_caveat_present": True,
            "explicit_caveat_label": "no_honest_local_next_change_question_remains_on_the_carried_same_12_case_baseline_after_governed_post_v0_15_reassessment",
            "next_primary_phase_question": "carried_baseline_evidence_exhaustion_transition_evaluation",
            "do_not_continue_v0_16_same_next_change_question_loop_by_default": True,
        },
    )
    _write_closeout(
        paths["v170"],
        {
            "version_decision": "v0_17_0_no_honest_transition_question_remains",
            "transition_governance_status": "governance_ready",
            "governance_ready_for_runtime_execution": False,
            "minimum_completion_signal_pass": False,
            "named_first_transition_pack_ready": False,
            "transition_arc_viability_status": "not_justified",
            "transition_governance_outcome": "no_honest_transition_question_remains",
            "v0_17_1_handoff_mode": "prepare_v0_17_phase_synthesis",
        },
    )
    _write_closeout(
        paths["v171"],
        {
            "version_decision": "v0_17_phase_nearly_complete_with_explicit_caveat",
            "phase_stop_condition_status": "nearly_complete_with_caveat",
            "explicit_caveat_present": True,
            "explicit_caveat_label": "no_honest_governed_transition_question_remains_on_the_carried_same_12_case_baseline_after_explicit_evidence_exhaustion_reassessment",
            "next_primary_phase_question": "post_transition_question_exhaustion_next_honest_move",
            "do_not_continue_v0_17_same_transition_question_loop_by_default": True,
            "v0_18_primary_phase_question": "post_transition_question_exhaustion_next_honest_move",
        },
    )
    return paths


class AgentModelicaV180NextHonestMoveGovernanceFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v180_handoff_integrity(
                v171_closeout_path=str(paths["v171"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v171"],
                {
                    "version_decision": "v0_17_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "no_honest_governed_transition_question_remains_on_the_carried_same_12_case_baseline_after_explicit_evidence_exhaustion_reassessment",
                    "next_primary_phase_question": "post_transition_question_exhaustion_next_honest_move",
                    "do_not_continue_v0_17_same_transition_question_loop_by_default": False,
                },
            )
            payload = build_v180_handoff_integrity(
                v171_closeout_path=str(paths["v171"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_evidence_boundary_readout_ready_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v180_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["evidence_boundary_readout"]["evidence_boundary_readout_status"], "ready")
            self.assertTrue(payload["evidence_boundary_readout"]["carried_local_question_exhaustion_confirmed"])
            self.assertTrue(payload["evidence_boundary_readout"]["carried_transition_question_exhaustion_confirmed"])

    def test_family_separation_ready_path_when_overlap_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v180_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["next_move_family_separation_rule"]["family_separation_status"], "ready")
            self.assertEqual(
                payload["next_move_family_separation_rule"]["strict_separation_table"][1]["family_name"],
                "governed_methodological_reframing_question",
            )

    def test_explicit_rejection_of_broad_unconstrained_restart_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            candidate_registry = {
                "candidate_rows": [
                    {
                        "candidate_id": "broad_unconstrained_restart_candidate",
                        "candidate_family": "governed_baseline_reset_with_loss_accounting",
                        "reframing_target": "replace_everything_and_restart_the_story",
                        "why_this_is_not_a_silent_restart": "it_is_a_silent_restart",
                        "what_remains_interpretable": "nothing",
                        "what_becomes_non_comparable": "everything",
                        "why_non_marginal_information_gain_still_exists": "",
                        "admission_status": "rejected",
                        "rejection_reason": "broad_unconstrained_restart_out_of_scope",
                    }
                ]
            }
            payload = build_v180_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                candidate_registry=candidate_registry,
                out_dir=str(root / "governance"),
            )
            self.assertIn(
                {
                    "candidate_id": "broad_unconstrained_restart_candidate",
                    "rejection_reason": "broad_unconstrained_restart_out_of_scope",
                },
                payload["next_move_admission"]["rejection_reason_table"],
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
                {"version_decision": "v0_11_2_first_product_gap_substrate_ready"},
                product_gap_substrate_builder={
                    "carried_baseline_source": "v0_10_3_frozen_12_case_real_origin_substrate",
                    "product_gap_candidate_table": broken_rows,
                },
            )
            payload = build_v180_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["baseline_continuity_check"]["baseline_continuity_check_status"], "broken")
            self.assertEqual(payload["next_honest_move_governance_status"], "governance_partial")

    def test_governance_partial_when_next_move_viability_is_not_justified(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            candidate_registry = {
                "candidate_rows": [
                    {
                        "candidate_id": "governed_methodological_reframing_v1",
                        "candidate_family": "governed_methodological_reframing_question",
                        "reframing_target": "reframe_the_project_conclusion_question",
                        "why_this_is_not_a_silent_restart": "the reframing is explicit and governed",
                        "what_remains_interpretable": "the carried evidence-boundary explanation",
                        "what_becomes_non_comparable": "same-evidence-object pre_post claims",
                        "why_non_marginal_information_gain_still_exists": "a distinct larger reframing question still exists",
                        "admission_status": "admitted",
                    }
                ]
            }
            governance_outcome = {
                "next_move_governance_outcome": "next_honest_move_exists",
                "named_governance_outcome_reason": "a_larger_reframing_question_exists_but_the_branch_is_still_not_justified",
            }
            payload = build_v180_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                candidate_registry=candidate_registry,
                governance_outcome=governance_outcome,
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["next_move_viability"]["next_move_viability_status"], "not_justified")
            self.assertEqual(payload["next_honest_move_governance_status"], "governance_partial")

    def test_closeout_path_when_no_honest_next_move_remains(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v180_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                out_dir=str(root / "governance"),
            )
            payload = build_v180_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_18_0_no_honest_next_move_remains")
            self.assertEqual(payload["conclusion"]["v0_18_1_handoff_mode"], "prepare_v0_18_phase_closeout_or_stop")

    def test_closeout_routes_to_governance_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            candidate_registry = {
                "candidate_rows": [
                    {
                        "candidate_id": "governed_methodological_reframing_v1",
                        "candidate_family": "governed_methodological_reframing_question",
                        "reframing_target": "reframe_the_project_conclusion_question",
                        "why_this_is_not_a_silent_restart": "the reframing is explicit and governed",
                        "what_remains_interpretable": "the carried evidence-boundary explanation",
                        "what_becomes_non_comparable": "same-evidence-object pre_post claims",
                        "why_non_marginal_information_gain_still_exists": "the reframing can answer a new honest methodological question",
                        "admission_status": "admitted",
                    }
                ]
            }
            viability_object = {
                "next_move_viability_status": "justified",
                "scope_relevant_uncertainty_remains": True,
                "named_viability_question": "Does an explicit methodological reframing reveal a more honest project-level conclusion than either change-candidate or transition-question branches could provide?",
                "expected_information_gain": "non_marginal",
                "concrete_first_pack_available": True,
                "next_move_still_possible": True,
                "named_reason_if_not_justified": "",
            }
            governance_outcome = {
                "next_move_governance_outcome": "next_honest_move_exists",
                "named_governance_outcome_reason": "a_larger_reframing_question_survives_admission_and_preserves_honesty",
            }
            build_v180_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                candidate_registry=candidate_registry,
                next_move_viability_object=viability_object,
                governance_outcome=governance_outcome,
                out_dir=str(root / "governance"),
            )
            payload = build_v180_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_18_0_next_honest_move_governance_ready")
            self.assertEqual(
                payload["conclusion"]["v0_18_1_handoff_mode"],
                "evaluate_first_next_honest_move_or_close_in_same_phase",
            )

    def test_closeout_routes_to_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v171"],
                {
                    "version_decision": "v0_17_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": False,
                    "explicit_caveat_label": "",
                    "next_primary_phase_question": "post_transition_question_exhaustion_next_honest_move",
                    "do_not_continue_v0_17_same_transition_question_loop_by_default": True,
                },
            )
            payload = build_v180_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v161_closeout_path=str(paths["v161"]),
                v170_closeout_path=str(paths["v170"]),
                v171_closeout_path=str(paths["v171"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_18_0_handoff_phase_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
