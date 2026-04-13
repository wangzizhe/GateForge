from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_15_1_closeout import build_v151_closeout
from gateforge.agent_modelica_v0_15_1_handoff_integrity import build_v151_handoff_integrity
from gateforge.agent_modelica_v0_15_1_viability_resolution import build_v151_viability_resolution


def _write_v150_closeout(path: Path, *, drift: bool = False) -> None:
    conclusion = {
        "version_decision": "v0_15_0_even_broader_change_governance_ready" if drift else "v0_15_0_even_broader_change_governance_partial",
        "even_broader_change_governance_status": "governance_ready" if drift else "governance_partial",
        "governance_ready_for_runtime_execution": bool(drift),
        "minimum_completion_signal_pass": bool(drift),
        "named_first_even_broader_change_pack_ready": False,
        "execution_arc_viability_status": "justified" if drift else "not_justified",
        "named_reason_if_not_justified": "" if drift else "admitted_broader_change_set_covers_available_scope_and_residual_gap_requires_broader_than_governed_change",
        "v0_15_1_handoff_mode": "execute_first_even_broader_change_pack" if drift else "resolve_v0_15_0_governance_or_viability_gaps_first",
    }
    payload = {
        "conclusion": conclusion,
        "governance_pack": {
            "pre_post_even_broader_change_comparison_protocol": {
                "baseline_execution_source": "agent_modelica_live_executor_v1",
                "post_change_execution_source_requirement": "agent_modelica_live_executor_v1",
                "same_case_requirement": True,
                "runtime_measurement_required": True,
            }
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV151EvenBroaderExecutionResolutionFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v150 = root / "v150.json"
            _write_v150_closeout(v150)
            payload = build_v151_handoff_integrity(v150_closeout_path=str(v150), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path_when_v150_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v150 = root / "v150.json"
            _write_v150_closeout(v150, drift=True)
            payload = build_v151_handoff_integrity(v150_closeout_path=str(v150), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_reassessment_path_remains_not_justified(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v150 = root / "v150.json"
            _write_v150_closeout(v150)
            payload = build_v151_viability_resolution(v150_closeout_path=str(v150), out_dir=str(root / "resolution"))
            self.assertEqual(payload["execution_arc_viability_reassessment_object"]["execution_arc_viability_status"], "not_justified")
            self.assertFalse(payload["first_even_broader_pack_readiness_object"]["named_first_even_broader_change_pack_ready"])

    def test_reassessment_path_becomes_justified(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v150 = root / "v150.json"
            _write_v150_closeout(v150)
            payload = build_v151_viability_resolution(
                v150_closeout_path=str(v150),
                out_dir=str(root / "resolution"),
                execution_arc_viability_status="justified",
                scope_relevant_uncertainty_remains=True,
                named_viability_question="Can a concrete governed model-family replacement change the failure-mode distribution on the carried baseline?",
                expected_information_gain="non_marginal",
                concrete_first_pack_available=True,
                same_source_comparison_still_possible=True,
                admitted_candidate_ids_if_ready=["governed_model_family_replacement_v1"],
            )
            self.assertEqual(payload["execution_arc_viability_reassessment_object"]["execution_arc_viability_status"], "justified")
            self.assertTrue(payload["first_even_broader_pack_readiness_object"]["named_first_even_broader_change_pack_ready"])

    def test_invalid_when_justified_but_no_admitted_candidate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v150 = root / "v150.json"
            _write_v150_closeout(v150)
            payload = build_v151_viability_resolution(
                v150_closeout_path=str(v150),
                out_dir=str(root / "resolution"),
                execution_arc_viability_status="justified",
                scope_relevant_uncertainty_remains=True,
                named_viability_question="Can an even-broader pack answer a still-open residual uncertainty?",
                expected_information_gain="non_marginal",
                concrete_first_pack_available=True,
                same_source_comparison_still_possible=True,
                admitted_candidate_ids_if_ready=[],
            )
            self.assertEqual(payload["execution_arc_viability_reassessment_object"]["execution_arc_viability_status"], "invalid")

    def test_closeout_routes_to_execution_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v150 = root / "v150.json"
            _write_v150_closeout(v150)
            build_v151_handoff_integrity(v150_closeout_path=str(v150), out_dir=str(root / "handoff"))
            build_v151_viability_resolution(
                v150_closeout_path=str(v150),
                out_dir=str(root / "resolution"),
                execution_arc_viability_status="justified",
                scope_relevant_uncertainty_remains=True,
                named_viability_question="Can a concrete even-broader pack answer a still-open residual uncertainty?",
                expected_information_gain="non_marginal",
                concrete_first_pack_available=True,
                same_source_comparison_still_possible=True,
                admitted_candidate_ids_if_ready=["cross_layer_execution_diagnosis_restructuring_v1"],
            )
            payload = build_v151_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                viability_resolution_path=str(root / "resolution" / "summary.json"),
                v150_closeout_path=str(v150),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_15_1_even_broader_execution_ready")
            self.assertEqual(payload["conclusion"]["v0_15_2_handoff_mode"], "execute_first_even_broader_change_pack")

    def test_closeout_routes_to_execution_not_justified(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v150 = root / "v150.json"
            _write_v150_closeout(v150)
            payload = build_v151_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                viability_resolution_path=str(root / "resolution" / "summary.json"),
                v150_closeout_path=str(v150),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_15_1_even_broader_execution_not_justified")
            self.assertEqual(payload["conclusion"]["v0_15_2_handoff_mode"], "prepare_v0_15_phase_synthesis")

    def test_closeout_routes_to_invalid_on_bad_handoff_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v150 = root / "v150.json"
            _write_v150_closeout(v150, drift=True)
            payload = build_v151_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                viability_resolution_path=str(root / "resolution" / "summary.json"),
                v150_closeout_path=str(v150),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_15_1_handoff_phase_inputs_invalid")
            self.assertEqual(payload["conclusion"]["v0_15_2_handoff_mode"], "rebuild_v0_15_1_phase_inputs_first")


if __name__ == "__main__":
    unittest.main()
