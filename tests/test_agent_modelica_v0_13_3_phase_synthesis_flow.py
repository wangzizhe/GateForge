from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_13_3_closeout import build_v133_closeout
from gateforge.agent_modelica_v0_13_3_meaning_synthesis import build_v133_meaning_synthesis
from gateforge.agent_modelica_v0_13_3_phase_ledger import build_v133_phase_ledger
from gateforge.agent_modelica_v0_13_3_stop_condition import build_v133_stop_condition


def _write_closeout(path: Path, version_decision: str, extra: dict | None = None) -> None:
    payload = {"conclusion": {"version_decision": version_decision}}
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v130": root / "v130" / "summary.json",
        "v131": root / "v131" / "summary.json",
        "v132": root / "v132" / "summary.json",
    }
    _write_closeout(
        paths["v130"],
        "v0_13_0_capability_intervention_governance_ready",
        {"v0_13_1_handoff_mode": "execute_first_bounded_capability_intervention_pack"},
    )
    _write_closeout(
        paths["v131"],
        "v0_13_1_first_capability_intervention_pack_side_evidence_only",
        {
            "intervention_effect_class": "side_evidence_only",
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_13_2_handoff_mode": "determine_whether_stronger_bounded_capability_intervention_is_in_scope",
        },
    )
    _write_closeout(
        paths["v132"],
        "v0_13_2_stronger_bounded_capability_intervention_not_in_scope",
        {
            "stronger_intervention_scope_status": "not_in_scope",
            "expected_information_gain": "marginal",
            "named_blocker_if_not_in_scope": (
                "admitted_bounded_intervention_set_covers_available_scope_and_residual_gap_requires_broader_capability_change"
            ),
            "v0_13_3_handoff_mode": "prepare_v0_13_phase_synthesis",
        },
    )
    return paths


class AgentModelicaV133PhaseSynthesisFlowTests(unittest.TestCase):

    def test_phase_ledger_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v133_phase_ledger(
                v130_closeout_path=str(paths["v130"]),
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "ready")
            self.assertTrue(payload["phase_primary_question_answered_enough_for_handoff"])

    def test_phase_ledger_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v131"], "v0_13_1_first_capability_intervention_pack_non_material")
            payload = build_v133_phase_ledger(
                v130_closeout_path=str(paths["v130"]),
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "invalid")

    def test_stop_condition_nearly_complete_with_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v133_stop_condition(
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "nearly_complete_with_caveat")
            self.assertTrue(payload["bounded_capability_intervention_effect_answered"])
            self.assertTrue(payload["stronger_bounded_capability_intervention_scope_answered"])
            self.assertFalse(payload["same_class_reopen_required"])

    def test_synthetic_met_input_routes_to_invalid_because_future_reserved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v133_phase_ledger(
                v130_closeout_path=str(paths["v130"]),
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "ledger"),
            )
            stop_dir = root / "stop"
            stop_dir.mkdir(parents=True, exist_ok=True)
            (stop_dir / "summary.json").write_text(
                json.dumps({"phase_stop_condition_status": "met"}),
                encoding="utf-8",
            )
            build_v133_meaning_synthesis(
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "meaning"),
            )
            payload = build_v133_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v130_closeout_path=str(paths["v130"]),
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_13_3_handoff_phase_inputs_invalid")
            self.assertEqual(
                payload["conclusion"]["v0_14_primary_phase_question"],
                "met_path_not_yet_in_scope_for_v0_13_3",
            )

    def test_stop_condition_not_ready_for_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v132"],
                "v0_13_2_stronger_bounded_capability_intervention_justified",
                {"v0_13_3_handoff_mode": "execute_stronger_bounded_capability_intervention"},
            )
            payload = build_v133_stop_condition(
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "not_ready_for_closeout")

    def test_meaning_synthesis_next_phase_selection(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v133_meaning_synthesis(
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "meaning"),
            )
            self.assertTrue(payload["explicit_caveat_present"])
            self.assertEqual(
                payload["next_primary_phase_question"],
                "post_bounded_capability_intervention_broader_change_evaluation",
            )
            self.assertTrue(payload["do_not_continue_v0_13_same_capability_intervention_refinement_by_default"])

    def test_closeout_nearly_complete_with_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v133_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v130_closeout_path=str(paths["v130"]),
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_13_phase_nearly_complete_with_explicit_caveat",
            )
            self.assertEqual(
                payload["conclusion"]["v0_14_primary_phase_question"],
                "post_bounded_capability_intervention_broader_change_evaluation",
            )
            self.assertTrue(payload["conclusion"]["explicit_caveat_present"])

    def test_invalid_when_nearly_complete_caveat_but_no_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v133_phase_ledger(
                v130_closeout_path=str(paths["v130"]),
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "ledger"),
            )
            build_v133_stop_condition(
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "stop"),
            )
            build_v133_meaning_synthesis(
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "meaning"),
            )
            meaning_path = root / "meaning" / "summary.json"
            meaning = json.loads(meaning_path.read_text(encoding="utf-8"))
            meaning["explicit_caveat_present"] = False
            meaning["explicit_caveat_label"] = ""
            meaning["do_not_continue_v0_13_same_capability_intervention_refinement_by_default"] = False
            meaning_path.write_text(json.dumps(meaning), encoding="utf-8")
            payload = build_v133_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(meaning_path),
                v130_closeout_path=str(paths["v130"]),
                v131_closeout_path=str(paths["v131"]),
                v132_closeout_path=str(paths["v132"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_13_3_handoff_phase_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
