from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_12_0_closeout import build_v120_closeout
from gateforge.agent_modelica_v0_12_0_governance_pack import build_v120_governance_pack
from gateforge.agent_modelica_v0_12_0_handoff_integrity import build_v120_handoff_integrity


def _write_closeout(path: Path, conclusion: dict, **extra: dict) -> None:
    payload = {"conclusion": conclusion}
    payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v111": root / "v111" / "summary.json",
        "v112": root / "v112" / "summary.json",
        "v115": root / "v115" / "summary.json",
        "v117": root / "v117" / "summary.json",
    }
    _write_closeout(
        paths["v111"],
        {
            "version_decision": "v0_11_1_first_product_gap_patch_pack_ready",
            "v0_11_2_handoff_mode": "freeze_first_product_gap_evaluation_substrate",
        },
    )
    _write_closeout(
        paths["v112"],
        {
            "version_decision": "v0_11_2_first_product_gap_substrate_ready",
            "v0_11_3_handoff_mode": "characterize_first_product_gap_profile",
        },
        product_gap_substrate_admission={"product_gap_substrate_size": 12},
    )
    _write_closeout(
        paths["v115"],
        {
            "version_decision": "v0_11_5_first_product_gap_profile_partial_but_interpretable",
            "formal_adjudication_label": "product_gap_partial_but_interpretable",
            "execution_posture_semantics_preserved": True,
            "dominant_gap_family_readout": "residual_core_capability_gap",
        },
    )
    _write_closeout(
        paths["v117"],
        {
            "version_decision": "v0_11_phase_nearly_complete_with_explicit_caveat",
            "phase_stop_condition_status": "nearly_complete_with_caveat",
            "explicit_caveat_present": True,
            "explicit_caveat_label": "product_gap_remains_partial_rather_than_product_ready_after_governed_workflow_to_product_evaluation",
            "next_primary_phase_question": "workflow_to_product_gap_operational_remedy_evaluation",
            "do_not_continue_v0_11_same_product_gap_refinement_by_default": True,
        },
    )
    return paths


class AgentModelicaV120OperationalRemedyGovernanceFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v120_handoff_integrity(
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v117_closeout_path=str(paths["v117"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v117"],
                {
                    "version_decision": "v0_11_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "product_gap_remains_partial_rather_than_product_ready_after_governed_workflow_to_product_evaluation",
                    "next_primary_phase_question": "workflow_to_product_gap_evaluation",
                    "do_not_continue_v0_11_same_product_gap_refinement_by_default": True,
                },
            )
            payload = build_v120_handoff_integrity(
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v117_closeout_path=str(paths["v117"]),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_baseline_anchor_pass_on_carried_v112_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v120_governance_pack(
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v117_closeout_path=str(paths["v117"]),
                out_dir=str(root / "governance"),
            )
            self.assertTrue(payload["baseline_anchor"]["baseline_anchor_pass"])
            self.assertEqual(
                payload["baseline_anchor"]["carried_product_gap_substrate_reference"],
                "v0_11_2_first_product_gap_substrate_ready",
            )

    def test_rejects_broad_capability_rewrite_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v120_governance_pack(
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v117_closeout_path=str(paths["v117"]),
                out_dir=str(root / "governance"),
            )
            rejection_table = payload["remedy_admission"]["rejection_reason_table"]
            self.assertIn(
                {
                    "remedy_id": "broad_capability_rewrite_candidate",
                    "rejection_reason": "disguised_broad_capability_rewrite",
                },
                rejection_table,
            )

    def test_rejects_task_base_widening_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v120_governance_pack(
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v117_closeout_path=str(paths["v117"]),
                out_dir=str(root / "governance"),
            )
            rejection_table = payload["remedy_admission"]["rejection_reason_table"]
            self.assertIn(
                {
                    "remedy_id": "task_base_widening_candidate",
                    "rejection_reason": "requires_task_base_widening",
                },
                rejection_table,
            )

    def test_closeout_routes_to_governance_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v120_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v117_closeout_path=str(paths["v117"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_12_0_operational_remedy_governance_ready")
            self.assertEqual(payload["conclusion"]["v0_12_1_handoff_mode"], "execute_first_bounded_operational_remedy_pack")

    def test_closeout_routes_to_governance_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            governance = build_v120_governance_pack(
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v117_closeout_path=str(paths["v117"]),
                runtime_remedy_evaluation_contract={
                    "required_runtime_evidence_fields": [
                        "remedy_id",
                        "pre_remedy_run_reference",
                    ],
                    "allowed_effect_claim_status_values": [
                        "mainline_improving",
                        "side_evidence_only",
                    ],
                    "runtime_remedy_evaluation_contract_frozen": False,
                },
                out_dir=str(root / "governance"),
            )
            self.assertEqual(governance["operational_remedy_governance_status"], "governance_partial")
            payload = build_v120_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v117_closeout_path=str(paths["v117"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_12_0_operational_remedy_governance_partial")
            self.assertEqual(
                payload["conclusion"]["v0_12_1_handoff_mode"],
                "finish_operational_remedy_governance_before_runtime_execution",
            )

    def test_closeout_routes_to_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v117"],
                {
                    "version_decision": "v0_11_phase_nearly_complete_with_explicit_caveat",
                    "phase_stop_condition_status": "nearly_complete_with_caveat",
                    "explicit_caveat_present": True,
                    "explicit_caveat_label": "product_gap_remains_partial_rather_than_product_ready_after_governed_workflow_to_product_evaluation",
                    "next_primary_phase_question": "workflow_to_product_gap_evaluation",
                    "do_not_continue_v0_11_same_product_gap_refinement_by_default": True,
                },
            )
            payload = build_v120_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v115_closeout_path=str(paths["v115"]),
                v117_closeout_path=str(paths["v117"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_12_0_operational_remedy_inputs_invalid")
            self.assertEqual(payload["conclusion"]["v0_12_1_handoff_mode"], "rebuild_operational_remedy_governance_first")


if __name__ == "__main__":
    unittest.main()
