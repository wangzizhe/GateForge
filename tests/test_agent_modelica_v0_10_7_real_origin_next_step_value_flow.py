from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_10_7_bounded_real_origin_step_worth_it_summary import (
    build_v107_bounded_real_origin_step_worth_it_summary,
)
from gateforge.agent_modelica_v0_10_7_closeout import build_v107_closeout
from gateforge.agent_modelica_v0_10_7_handoff_integrity import build_v107_handoff_integrity
from gateforge.agent_modelica_v0_10_7_remaining_uncertainty_characterization import (
    build_v107_remaining_uncertainty_characterization,
)


class AgentModelicaV107RealOriginNextStepValueFlowTests(unittest.TestCase):
    def _write_v106_closeout(self, path: Path, *, dominant_share_justified: bool = False) -> None:
        distribution = (
            {
                "extractive_conversion_chain_unresolved": 6,
                "multibody_constraint_chain_unresolved": 1,
                "library_validation_chain_unresolved": 1,
            }
            if dominant_share_justified
            else {
                "extractive_conversion_chain_unresolved": 3,
                "multibody_constraint_chain_unresolved": 1,
                "library_validation_chain_unresolved": 2,
                "interface_fragility_after_surface_fix": 1,
                "artifact_gap_after_surface_fix": 1,
            }
        )
        payload = {
            "conclusion": {
                "version_decision": "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable",
                "final_adjudication_label": "real_origin_workflow_readiness_partial_but_interpretable",
                "supported_check_pass": False,
                "partial_check_pass": True,
                "fallback_triggered": False,
                "execution_posture_semantics_preserved": True,
                "v0_10_7_handoff_mode": "decide_whether_one_more_bounded_real_origin_step_is_still_worth_it",
            },
            "real_origin_adjudication_input_table": {
                "non_success_label_distribution": distribution,
            },
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_handoff_integrity_passes_on_partial_real_origin_adjudication(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v106_closeout = root / "v106_closeout.json"
            self._write_v106_closeout(v106_closeout)
            payload = build_v107_handoff_integrity(
                v106_closeout_path=str(v106_closeout),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["status"], "PASS")

    def test_remaining_uncertainty_characterization_marks_not_worth_it_on_real_shape(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v106_closeout = root / "v106_closeout.json"
            self._write_v106_closeout(v106_closeout)
            payload = build_v107_remaining_uncertainty_characterization(
                v106_closeout_path=str(v106_closeout),
                out_dir=str(root / "uncertainty"),
            )
            self.assertEqual(payload["remaining_uncertainty_status"], "no_phase_relevant_uncertainty_remaining")
            self.assertEqual(payload["expected_information_gain"], "marginal")
            self.assertEqual(payload["candidate_next_step_shape"], "none")

    def test_summary_marks_not_worth_it_and_uses_none_step_kind(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v106_closeout = root / "v106_closeout.json"
            self._write_v106_closeout(v106_closeout)
            build_v107_remaining_uncertainty_characterization(
                v106_closeout_path=str(v106_closeout),
                out_dir=str(root / "uncertainty"),
            )
            payload = build_v107_bounded_real_origin_step_worth_it_summary(
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            self.assertEqual(payload["bounded_real_origin_step_worth_it_status"], "more_bounded_real_origin_step_not_worth_it")
            self.assertEqual(payload["proposed_next_step_kind"], "none")
            self.assertEqual(payload["expected_information_gain"], "marginal")

    def test_closeout_reaches_not_worth_it_on_real_shape(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v106_closeout = root / "v106_closeout.json"
            self._write_v106_closeout(v106_closeout)
            payload = build_v107_closeout(
                v106_closeout_path=str(v106_closeout),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                bounded_real_origin_step_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_7_more_bounded_real_origin_step_not_worth_it")
            self.assertEqual(payload["conclusion"]["v0_10_8_handoff_mode"], "prepare_v0_10_phase_synthesis")

    def test_justified_path_is_executable_with_strongly_concentrated_synthetic_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v106_closeout = root / "v106_closeout.json"
            self._write_v106_closeout(v106_closeout, dominant_share_justified=True)
            build_v107_remaining_uncertainty_characterization(
                v106_closeout_path=str(v106_closeout),
                out_dir=str(root / "uncertainty"),
            )
            build_v107_bounded_real_origin_step_worth_it_summary(
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            payload = build_v107_closeout(
                v106_closeout_path=str(v106_closeout),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                bounded_real_origin_step_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_7_one_more_bounded_real_origin_step_justified")
            self.assertEqual(
                payload["conclusion"]["proposed_next_step_kind"],
                "targeted_non_success_family_clarification",
            )

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_v106 = root / "bad_v106_closeout.json"
            bad_payload = {
                "conclusion": {
                    "version_decision": "v0_10_6_first_real_origin_workflow_readiness_supported",
                    "final_adjudication_label": "real_origin_workflow_readiness_supported",
                    "supported_check_pass": True,
                    "partial_check_pass": False,
                    "fallback_triggered": False,
                    "execution_posture_semantics_preserved": True,
                    "v0_10_7_handoff_mode": "prepare_v0_10_phase_synthesis",
                }
            }
            bad_v106.write_text(json.dumps(bad_payload), encoding="utf-8")
            payload = build_v107_closeout(
                v106_closeout_path=str(bad_v106),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                bounded_real_origin_step_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_7_real_origin_next_step_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
