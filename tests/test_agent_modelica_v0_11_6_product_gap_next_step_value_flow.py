from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_11_6_bounded_product_gap_step_worth_it_summary import (
    build_v116_bounded_product_gap_step_worth_it_summary,
)
from gateforge.agent_modelica_v0_11_6_closeout import build_v116_closeout
from gateforge.agent_modelica_v0_11_6_handoff_integrity import build_v116_handoff_integrity
from gateforge.agent_modelica_v0_11_6_remaining_uncertainty_characterization import (
    build_v116_remaining_uncertainty_characterization,
)


class AgentModelicaV116ProductGapNextStepValueFlowTests(unittest.TestCase):
    def _write_v115_closeout(
        self,
        path: Path,
        *,
        dominant_gap_family_readout: str = "residual_core_capability_gap",
        bad_handoff: bool = False,
    ) -> None:
        payload = {
            "conclusion": {
                "version_decision": (
                    "v0_11_5_product_gap_adjudication_inputs_invalid"
                    if bad_handoff
                    else "v0_11_5_first_product_gap_profile_partial_but_interpretable"
                ),
                "formal_adjudication_label": (
                    "product_gap_fallback" if bad_handoff else "product_gap_partial_but_interpretable"
                ),
                "supported_check_pass": False,
                "partial_check_pass": False if bad_handoff else True,
                "fallback_triggered": True if bad_handoff else False,
                "execution_posture_semantics_preserved": True,
                "dominant_gap_family_readout": dominant_gap_family_readout,
                "v0_11_6_handoff_mode": (
                    "rebuild_product_gap_adjudication_inputs_first"
                    if bad_handoff
                    else "decide_whether_one_more_bounded_product_gap_step_is_still_worth_it"
                ),
            }
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v115_closeout = root / "v115_closeout.json"
            self._write_v115_closeout(v115_closeout)
            payload = build_v116_handoff_integrity(
                v115_closeout_path=str(v115_closeout),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_v115 = root / "bad_v115_closeout.json"
            self._write_v115_closeout(bad_v115, bad_handoff=True)
            payload = build_v116_handoff_integrity(
                v115_closeout_path=str(bad_v115),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["status"], "FAIL")

    def test_not_worth_it_path_on_real_frozen_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v115_closeout = root / "v115_closeout.json"
            self._write_v115_closeout(v115_closeout)
            payload = build_v116_closeout(
                v115_closeout_path=str(v115_closeout),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                bounded_product_gap_step_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_6_more_bounded_product_gap_step_not_worth_it")
            self.assertEqual(payload["conclusion"]["v0_11_7_handoff_mode"], "prepare_v0_11_phase_synthesis")
            self.assertEqual(payload["conclusion"]["proposed_next_step_kind"], "none")

    def test_justified_path_under_synthetic_context_discipline_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v115_closeout = root / "v115_closeout.json"
            self._write_v115_closeout(v115_closeout, dominant_gap_family_readout="context_discipline_gap")
            build_v116_remaining_uncertainty_characterization(
                v115_closeout_path=str(v115_closeout),
                out_dir=str(root / "uncertainty"),
            )
            build_v116_bounded_product_gap_step_worth_it_summary(
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            payload = build_v116_closeout(
                v115_closeout_path=str(v115_closeout),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                bounded_product_gap_step_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_6_one_more_bounded_product_gap_step_justified")
            self.assertEqual(
                payload["conclusion"]["proposed_next_step_kind"],
                "targeted_context_contract_clarification",
            )

    def test_not_worth_it_when_uncertainty_is_not_phase_relevant(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            uncertainty_path = root / "uncertainty" / "summary.json"
            uncertainty_path.parent.mkdir(parents=True, exist_ok=True)
            uncertainty_payload = {
                "remaining_uncertainty_status": "phase_relevant_but_not_step_addressable",
                "remaining_uncertainty_label": "mechanism_detail_only",
                "remaining_uncertainty_is_step_addressable": True,
                "remaining_uncertainty_is_phase_relevant": False,
                "expected_information_gain": "non_marginal",
                "candidate_next_step_shape": "targeted_context_contract_clarification",
            }
            uncertainty_path.write_text(json.dumps(uncertainty_payload), encoding="utf-8")
            summary = build_v116_bounded_product_gap_step_worth_it_summary(
                remaining_uncertainty_characterization_path=str(uncertainty_path),
                out_dir=str(root / "summary"),
            )
            self.assertEqual(summary["bounded_product_gap_step_worth_it_status"], "more_bounded_product_gap_step_not_worth_it")
            self.assertEqual(summary["proposed_next_step_kind"], "none")

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_v115 = root / "bad_v115_closeout.json"
            self._write_v115_closeout(bad_v115, bad_handoff=True)
            payload = build_v116_closeout(
                v115_closeout_path=str(bad_v115),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remaining_uncertainty_characterization_path=str(root / "uncertainty" / "summary.json"),
                bounded_product_gap_step_worth_it_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_6_product_gap_next_step_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
