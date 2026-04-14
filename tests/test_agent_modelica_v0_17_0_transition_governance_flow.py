from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_17_0_closeout import build_v170_closeout
from gateforge.agent_modelica_v0_17_0_governance_pack import build_v170_governance_pack
from gateforge.agent_modelica_v0_17_0_handoff_integrity import build_v170_handoff_integrity


def _write_closeout(path: Path, conclusion: dict, **extra: dict) -> None:
    payload = {"conclusion": conclusion}
    payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v112": root / "v112" / "summary.json",
        "v160": root / "v160" / "summary.json",
        "v161": root / "v161" / "summary.json",
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
        paths["v160"],
        {
            "version_decision": "v0_16_0_no_honest_next_change_question_remains",
            "next_change_question_governance_status": "governance_ready",
            "governance_ready_for_runtime_execution": False,
            "minimum_completion_signal_pass": False,
            "named_first_next_change_pack_ready": False,
            "next_arc_viability_status": "not_justified",
            "next_change_governance_outcome": "no_honest_next_local_change_question_remains",
            "v0_16_1_handoff_mode": "prepare_v0_16_phase_synthesis",
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
            "v0_17_primary_phase_question": "carried_baseline_evidence_exhaustion_transition_evaluation",
        },
    )
    return paths


class AgentModelicaV170TransitionGovernanceFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v170_handoff_integrity(
                v161_closeout_path=str(paths["v161"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v161"],
                {
                    "version_decision": "v0_16_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "no_honest_local_next_change_question_remains_on_the_carried_same_12_case_baseline_after_governed_post_v0_15_reassessment",
                    "next_primary_phase_question": "carried_baseline_evidence_exhaustion_transition_evaluation",
                    "do_not_continue_v0_16_same_next_change_question_loop_by_default": False,
                },
            )
            payload = build_v170_handoff_integrity(
                v161_closeout_path=str(paths["v161"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_carried_evidence_exhaustion_readout_ready_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v170_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(
                payload["carried_evidence_exhaustion_readout"]["carried_evidence_exhaustion_readout_status"],
                "ready",
            )
            self.assertTrue(payload["carried_evidence_exhaustion_readout"]["carried_local_question_exhaustion_confirmed"])

    def test_family_separation_ready_path_when_overlap_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v170_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["transition_family_separation_rule"]["family_separation_status"], "ready")
            self.assertEqual(
                payload["transition_family_separation_rule"]["strict_separation_table"][1]["family_name"],
                "governed_evaluation_object_transition",
            )

    def test_explicit_rejection_of_broad_unconstrained_replacement_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            candidate_registry = {
                "candidate_rows": [
                    {
                        "candidate_id": "broad_unconstrained_replacement_candidate",
                        "candidate_family": "governed_evidence_object_transition",
                        "transition_target": "replace_everything_without_a_transition_contract",
                        "target_gap_family": "residual_core_capability_gap",
                        "expected_effect_type": "unbounded_transition",
                        "what_remains_comparable": "nothing",
                        "what_no_longer_has_same_baseline_meaning": "everything",
                        "why_transition_is_interpretable": "",
                        "why_non_marginal_information_gain_still_exists": "",
                        "admission_status": "rejected",
                        "rejection_reason": "broad_unconstrained_rewrite_out_of_scope",
                    }
                ]
            }
            payload = build_v170_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                candidate_registry=candidate_registry,
                out_dir=str(root / "governance"),
            )
            self.assertIn(
                {
                    "candidate_id": "broad_unconstrained_replacement_candidate",
                    "rejection_reason": "broad_unconstrained_rewrite_out_of_scope",
                },
                payload["transition_admission"]["rejection_reason_table"],
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
            payload = build_v170_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["baseline_continuity_check"]["baseline_continuity_check_status"], "broken")
            self.assertEqual(payload["transition_governance_status"], "governance_partial")

    def test_governance_partial_when_transition_arc_viability_is_not_justified(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            candidate_registry = {
                "candidate_rows": [
                    {
                        "candidate_id": "governed_evaluation_object_transition_v2",
                        "candidate_family": "governed_evaluation_object_transition",
                        "transition_target": "move_to_new_governed_evaluation_object",
                        "target_gap_family": "residual_core_capability_gap",
                        "expected_effect_type": "evaluation_object_transition",
                        "what_remains_comparable": "the carried exhaustion readout",
                        "what_no_longer_has_same_baseline_meaning": "same-baseline pre_post deltas",
                        "why_transition_is_interpretable": "the transition contract is explicit",
                        "why_non_marginal_information_gain_still_exists": "a distinct governed question still exists",
                        "admission_status": "admitted",
                    }
                ]
            }
            governance_outcome = {
                "transition_governance_outcome": "next_honest_transition_question_exists",
                "named_governance_outcome_reason": "a_transition_question_exists_but_the_arc_is_still_not_justified",
            }
            payload = build_v170_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                candidate_registry=candidate_registry,
                governance_outcome=governance_outcome,
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["transition_arc_viability"]["transition_arc_viability_status"], "not_justified")
            self.assertEqual(payload["transition_governance_status"], "governance_partial")

    def test_closeout_path_when_no_honest_transition_question_remains(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v170_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                out_dir=str(root / "governance"),
            )
            payload = build_v170_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_17_0_no_honest_transition_question_remains")
            self.assertEqual(payload["conclusion"]["v0_17_1_handoff_mode"], "prepare_v0_17_phase_synthesis")

    def test_closeout_routes_to_governance_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            candidate_registry = {
                "candidate_rows": [
                    {
                        "candidate_id": "governed_evaluation_object_transition_v2",
                        "candidate_family": "governed_evaluation_object_transition",
                        "transition_target": "move_to_new_governed_evaluation_object",
                        "target_gap_family": "residual_core_capability_gap",
                        "expected_effect_type": "evaluation_object_transition",
                        "what_remains_comparable": "the carried exhaustion reason and the named comparability limits",
                        "what_no_longer_has_same_baseline_meaning": "same-baseline pre_post deltas on the original product-gap question",
                        "why_transition_is_interpretable": "the new question is explicit and auditable",
                        "why_non_marginal_information_gain_still_exists": "the new governed question can answer whether the evaluation object, not just the baseline, is exhausted",
                        "admission_status": "admitted",
                    }
                ]
            }
            viability_object = {
                "transition_arc_viability_status": "justified",
                "scope_relevant_uncertainty_remains": True,
                "named_viability_question": "Does a governed evaluation-object transition reveal a meaningfully different reading than the carried evidence-exhaustion readout?",
                "expected_information_gain": "non_marginal",
                "concrete_first_pack_available": True,
                "transition_still_possible": True,
                "named_reason_if_not_justified": "",
            }
            governance_outcome = {
                "transition_governance_outcome": "next_honest_transition_question_exists",
                "named_governance_outcome_reason": "a_governed_transition_question_survives_admission_and_preserves_interpretability",
            }
            build_v170_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                candidate_registry=candidate_registry,
                transition_arc_viability_object=viability_object,
                governance_outcome=governance_outcome,
                out_dir=str(root / "governance"),
            )
            payload = build_v170_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_17_0_transition_governance_ready")
            self.assertEqual(payload["conclusion"]["v0_17_1_handoff_mode"], "execute_first_transition_question_pack")

    def test_closeout_routes_to_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v161"],
                {
                    "version_decision": "v0_16_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": False,
                    "explicit_caveat_label": "",
                    "next_primary_phase_question": "carried_baseline_evidence_exhaustion_transition_evaluation",
                    "do_not_continue_v0_16_same_next_change_question_loop_by_default": True,
                },
            )
            payload = build_v170_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v160_closeout_path=str(paths["v160"]),
                v161_closeout_path=str(paths["v161"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_17_0_handoff_phase_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
