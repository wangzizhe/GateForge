from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_14_0_closeout import build_v140_closeout
from gateforge.agent_modelica_v0_14_0_governance_pack import build_v140_governance_pack
from gateforge.agent_modelica_v0_14_0_handoff_integrity import build_v140_handoff_integrity


def _write_closeout(path: Path, conclusion: dict, **extra: dict) -> None:
    payload = {"conclusion": conclusion}
    payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v112": root / "v112" / "summary.json",
        "v115": root / "v115" / "summary.json",
        "v133": root / "v133" / "summary.json",
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
        paths["v115"],
        {
            "version_decision": "v0_11_5_first_product_gap_profile_partial_but_interpretable",
            "formal_adjudication_label": "product_gap_partial_but_interpretable",
            "dominant_gap_family_readout": "residual_core_capability_gap",
        },
    )
    _write_closeout(
        paths["v133"],
        {
            "version_decision": "v0_13_phase_nearly_complete_with_explicit_caveat",
            "phase_stop_condition_status": "nearly_complete_with_caveat",
            "explicit_caveat_present": True,
            "explicit_caveat_label": "bounded_capability_interventions_side_evidence_only_and_stronger_bounded_escalation_not_in_scope_after_governed_same_source_evaluation",
            "next_primary_phase_question": "post_bounded_capability_intervention_broader_change_evaluation",
            "do_not_continue_v0_13_same_capability_intervention_refinement_by_default": True,
        },
    )
    return paths


class AgentModelicaV140BroaderChangeGovernanceFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v140_handoff_integrity(
                v133_closeout_path=str(paths["v133"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v133"],
                {
                    "version_decision": "v0_13_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "bounded_capability_interventions_side_evidence_only_and_stronger_bounded_escalation_not_in_scope_after_governed_same_source_evaluation",
                    "next_primary_phase_question": "capability_level_improvement_evaluation_after_operational_remedy_exhaustion",
                    "do_not_continue_v0_13_same_capability_intervention_refinement_by_default": True,
                },
            )
            payload = build_v140_handoff_integrity(
                v133_closeout_path=str(paths["v133"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_baseline_anchor_pass_on_carried_v133_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v140_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v133_closeout_path=str(paths["v133"]),
                out_dir=str(root / "governance"),
            )
            self.assertTrue(payload["broader_change_baseline_anchor"]["baseline_anchor_pass"])
            self.assertEqual(payload["broader_change_baseline_anchor"]["carried_phase_closeout_version"], "v0_13_3")

    def test_family_separation_ready_path_when_overlap_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v140_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v133_closeout_path=str(paths["v133"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["broader_change_family_separation_rule"]["family_separation_status"], "ready")
            self.assertEqual(
                payload["broader_change_family_separation_rule"]["strict_separation_table"][0]["family_name"],
                "broader_execution_policy_restructuring",
            )

    def test_rejects_broad_unconstrained_model_family_replacement_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v140_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v133_closeout_path=str(paths["v133"]),
                out_dir=str(root / "governance"),
            )
            self.assertIn(
                {
                    "candidate_id": "broad_unconstrained_model_family_replacement_candidate",
                    "rejection_reason": "broad_unconstrained_model_family_replacement_out_of_scope",
                },
                payload["broader_change_admission"]["rejection_reason_table"],
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
                    "v0_11_3_handoff_mode": "characterize_first_product_gap_profile",
                },
                product_gap_substrate_builder={
                    "carried_baseline_source": "v0_10_3_frozen_12_case_real_origin_substrate",
                    "product_gap_candidate_table": broken_rows,
                },
            )
            payload = build_v140_governance_pack(
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v133_closeout_path=str(paths["v133"]),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["baseline_continuity_check"]["baseline_continuity_check_status"], "broken")
            self.assertEqual(payload["capability_broader_change_governance_status"], "governance_partial")
            self.assertFalse(payload["governance_ready_for_runtime_execution"])

    def test_closeout_routes_to_governance_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v140_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v133_closeout_path=str(paths["v133"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_14_0_broader_change_governance_ready")
            self.assertEqual(payload["conclusion"]["v0_14_1_handoff_mode"], "execute_first_broader_change_pack")

    def test_closeout_routes_to_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v133"],
                {
                    "version_decision": "v0_13_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "bounded_capability_interventions_side_evidence_only_and_stronger_bounded_escalation_not_in_scope_after_governed_same_source_evaluation",
                    "next_primary_phase_question": "capability_level_improvement_evaluation_after_operational_remedy_exhaustion",
                    "do_not_continue_v0_13_same_capability_intervention_refinement_by_default": True,
                },
            )
            payload = build_v140_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v133_closeout_path=str(paths["v133"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_14_0_handoff_phase_inputs_invalid")
            self.assertEqual(payload["conclusion"]["v0_14_1_handoff_mode"], "rebuild_v0_14_0_phase_inputs_first")


if __name__ == "__main__":
    unittest.main()
