from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_16_0_closeout import build_v160_closeout
from gateforge.agent_modelica_v0_16_0_governance_pack import build_v160_governance_pack
from gateforge.agent_modelica_v0_16_0_handoff_integrity import build_v160_handoff_integrity


def _write_closeout(path: Path, conclusion: dict, **extra: dict) -> None:
    payload = {"conclusion": conclusion}
    payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v112": root / "v112" / "summary.json",
        "v150": root / "v150" / "summary.json",
        "v151": root / "v151" / "summary.json",
        "v152": root / "v152" / "summary.json",
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
        paths["v150"],
        {
            "version_decision": "v0_15_0_even_broader_change_governance_partial",
            "even_broader_change_governance_status": "governance_partial",
            "governance_ready_for_runtime_execution": False,
            "execution_arc_viability_status": "not_justified",
            "v0_15_1_handoff_mode": "resolve_v0_15_0_governance_or_viability_gaps_first",
        },
    )
    _write_closeout(
        paths["v151"],
        {
            "version_decision": "v0_15_1_even_broader_execution_not_justified",
            "execution_arc_viability_status": "not_justified",
            "named_first_even_broader_change_pack_ready": False,
            "named_reason_if_not_justified": "admitted_broader_change_set_covers_available_scope_and_residual_gap_requires_broader_than_governed_change",
            "v0_15_2_handoff_mode": "prepare_v0_15_phase_synthesis",
        },
    )
    _write_closeout(
        paths["v152"],
        {
            "version_decision": "v0_15_phase_nearly_complete_with_explicit_caveat",
            "phase_stop_condition_status": "nearly_complete_with_caveat",
            "explicit_caveat_present": True,
            "explicit_caveat_label": "even_broader_change_governance_was_frozen_but_execution_arc_viability_remained_not_justified_on_the_carried_same_source_baseline",
            "next_primary_phase_question": "post_even_broader_change_viability_exhaustion_next_change_question",
            "do_not_continue_v0_15_same_even_broader_refinement_by_default": True,
        },
    )
    return paths


class AgentModelicaV160NextChangeQuestionGovernanceFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v160_handoff_integrity(
                v152_closeout_path=str(paths["v152"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v152"],
                {
                    "version_decision": "v0_15_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "even_broader_change_governance_was_frozen_but_execution_arc_viability_remained_not_justified_on_the_carried_same_source_baseline",
                    "next_primary_phase_question": "post_even_broader_change_viability_exhaustion_next_change_question",
                    "do_not_continue_v0_15_same_even_broader_refinement_by_default": False,
                },
            )
            payload = build_v160_handoff_integrity(
                v152_closeout_path=str(paths["v152"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_baseline_anchor_pass_on_carried_v152_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v160_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                out_dir=str(root / "governance"),
            )
            self.assertTrue(payload["next_change_baseline_anchor"]["baseline_anchor_pass"])
            self.assertEqual(payload["next_change_baseline_anchor"]["carried_phase_closeout_version"], "v0_15_2")

    def test_family_separation_ready_path_when_overlap_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v160_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["next_change_family_separation_rule"]["family_separation_status"], "ready")
            self.assertEqual(
                payload["next_change_family_separation_rule"]["strict_separation_table"][0]["family_name"],
                "governed_baseline_rebuild_question",
            )

    def test_explicit_rejection_of_broad_unconstrained_replacement_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            candidate_registry = {
                "candidate_rows": [
                    {
                        "candidate_id": "broad_unconstrained_replacement_candidate",
                        "candidate_family": "governed_cross_stack_replacement_question",
                        "target_gap_family": "residual_core_capability_gap",
                        "target_failure_mode": "everything_needs_replacement",
                        "expected_effect_type": "mainline_workflow_improvement",
                        "next_change_surface": "full_unbounded_system_replacement",
                        "why_beyond_v0_15": "Replaces everything without preserving a governed transition contract.",
                        "why_still_honest_to_compare": "",
                        "admission_status": "rejected",
                        "rejection_reason": "broad_unconstrained_rewrite_out_of_scope",
                    }
                ]
            }
            payload = build_v160_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                candidate_registry=candidate_registry,
                governance_outcome={
                    "next_change_governance_outcome": "no_honest_next_local_change_question_remains",
                    "named_governance_outcome_reason": "no_bounded_or_transition_candidate_preserves_an_honest_governed_question",
                },
                out_dir=str(root / "governance"),
            )
            self.assertIn(
                {
                    "candidate_id": "broad_unconstrained_replacement_candidate",
                    "rejection_reason": "broad_unconstrained_rewrite_out_of_scope",
                },
                payload["next_change_admission"]["rejection_reason_table"],
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
            payload = build_v160_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["baseline_continuity_check"]["baseline_continuity_check_status"], "broken")
            self.assertEqual(payload["next_change_question_governance_status"], "governance_partial")
            self.assertFalse(payload["governance_ready_for_runtime_execution"])

    def test_governance_partial_when_next_arc_viability_is_not_justified(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v160_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                governance_outcome={
                    "next_change_governance_outcome": "next_honest_governed_question_exists",
                    "named_governance_outcome_reason": "a_transition_question_exists_but_the_arc_is_still_not_justified",
                },
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["next_arc_viability"]["next_arc_viability_status"], "not_justified")
            self.assertEqual(payload["next_change_question_governance_status"], "governance_partial")

    def test_routes_to_no_honest_next_change_question_remains_when_outcome_is_no_honest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v160_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                out_dir=str(root / "governance"),
            )
            payload = build_v160_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_16_0_no_honest_next_change_question_remains")
            self.assertEqual(payload["conclusion"]["v0_16_1_handoff_mode"], "prepare_v0_16_phase_synthesis")

    def test_closeout_routes_to_governance_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            candidate_registry = {
                "candidate_rows": [
                    {
                        "candidate_id": "governed_evaluation_object_transition_v1",
                        "candidate_family": "governed_evaluation_object_transition",
                        "target_gap_family": "residual_core_capability_gap",
                        "target_failure_mode": "the_carried_question_is_no_longer_the_most_honest_evaluation_object",
                        "expected_effect_type": "evaluation_object_transition",
                        "next_change_surface": "transition_to_a_governed_new_evaluation_object",
                        "why_beyond_v0_15": "This is beyond even-broader intervention because it changes the question rather than trying another larger local intervention.",
                        "why_still_honest_to_compare": "The transition contract names what remains comparable, what no longer has same-baseline semantics, and why the transition is auditable.",
                        "admission_status": "admitted",
                    }
                ]
            }
            viability_object = {
                "next_arc_viability_status": "justified",
                "scope_relevant_uncertainty_remains": True,
                "named_viability_question": "Does a governed evaluation-object transition reveal a materially different reading of the carried residual gap than further local intervention questions can provide?",
                "expected_information_gain": "non_marginal",
                "concrete_first_pack_available": True,
                "comparison_or_transition_still_possible": True,
                "named_reason_if_not_justified": "",
            }
            governance_outcome = {
                "next_change_governance_outcome": "next_honest_governed_question_exists",
                "named_governance_outcome_reason": "a_governed_transition_question_survives_admission_and_preserves_interpretability",
            }
            build_v160_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                candidate_registry=candidate_registry,
                next_arc_viability_object=viability_object,
                governance_outcome=governance_outcome,
                out_dir=str(root / "governance"),
            )
            payload = build_v160_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_16_0_next_change_question_governance_ready")
            self.assertEqual(payload["conclusion"]["v0_16_1_handoff_mode"], "execute_first_next_change_question_pack")

    def test_closeout_routes_to_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v152"],
                {
                    "version_decision": "v0_15_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "even_broader_change_governance_was_frozen_but_execution_arc_viability_remained_not_justified_on_the_carried_same_source_baseline",
                    "next_primary_phase_question": "post_even_broader_change_viability_exhaustion_next_change_question",
                    "do_not_continue_v0_15_same_even_broader_refinement_by_default": False,
                },
            )
            payload = build_v160_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v150_closeout_path=str(paths["v150"]),
                v151_closeout_path=str(paths["v151"]),
                v152_closeout_path=str(paths["v152"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_16_0_handoff_phase_inputs_invalid")
            self.assertEqual(payload["conclusion"]["v0_16_1_handoff_mode"], "rebuild_v0_16_0_phase_inputs_first")


if __name__ == "__main__":
    unittest.main()
