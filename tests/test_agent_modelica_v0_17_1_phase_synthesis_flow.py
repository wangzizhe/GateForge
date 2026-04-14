from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_17_1_closeout import build_v171_closeout
from gateforge.agent_modelica_v0_17_1_meaning_synthesis import build_v171_meaning_synthesis
from gateforge.agent_modelica_v0_17_1_phase_ledger import build_v171_phase_ledger
from gateforge.agent_modelica_v0_17_1_stop_condition import build_v171_stop_condition


def _write_closeout(path: Path, version_decision: str, extra: dict | None = None) -> None:
    payload = {"conclusion": {"version_decision": version_decision}}
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v170": root / "v170" / "summary.json",
    }
    _write_closeout(
        paths["v170"],
        "v0_17_0_no_honest_transition_question_remains",
        {
            "transition_governance_status": "governance_ready",
            "governance_ready_for_runtime_execution": False,
            "minimum_completion_signal_pass": False,
            "named_first_transition_pack_ready": False,
            "transition_arc_viability_status": "not_justified",
            "transition_governance_outcome": "no_honest_transition_question_remains",
            "why_this_is_or_is_not_ready": "The governance layer froze successfully enough to conclude that no honest transition question remains beyond the carried baseline evidence-exhaustion readout.",
            "v0_17_1_handoff_mode": "prepare_v0_17_phase_synthesis",
        },
    )
    return paths


class AgentModelicaV171PhaseSynthesisFlowTests(unittest.TestCase):
    def test_phase_ledger_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v171_phase_ledger(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "ready")
            self.assertTrue(payload["phase_primary_question_answered_enough_for_handoff"])

    def test_phase_ledger_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v170"], "v0_17_0_transition_governance_partial")
            payload = build_v171_phase_ledger(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "invalid")

    def test_stop_condition_nearly_complete_with_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v171_stop_condition(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "nearly_complete_with_caveat")
            self.assertTrue(payload["transition_governance_question_answered"])
            self.assertTrue(payload["no_honest_transition_question_answered"])
            self.assertFalse(payload["same_class_reopen_required"])

    def test_synthetic_met_input_routes_to_invalid_because_future_reserved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v171_phase_ledger(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "ledger"),
            )
            stop_dir = root / "stop"
            stop_dir.mkdir(parents=True, exist_ok=True)
            (stop_dir / "summary.json").write_text(
                json.dumps({"phase_stop_condition_status": "met"}),
                encoding="utf-8",
            )
            build_v171_meaning_synthesis(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "meaning"),
            )
            payload = build_v171_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_17_1_handoff_phase_inputs_invalid")
            self.assertEqual(
                payload["conclusion"]["v0_18_primary_phase_question"],
                "met_path_not_yet_in_scope_for_v0_17_1",
            )

    def test_stop_condition_not_ready_for_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v170"], "v0_17_0_transition_governance_partial")
            payload = build_v171_stop_condition(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "not_ready_for_closeout")

    def test_meaning_synthesis_next_phase_selection(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v171_meaning_synthesis(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "meaning"),
            )
            self.assertTrue(payload["explicit_caveat_present"])
            self.assertEqual(
                payload["next_primary_phase_question"],
                "post_transition_question_exhaustion_next_honest_move",
            )
            self.assertTrue(payload["do_not_continue_v0_17_same_transition_question_loop_by_default"])

    def test_closeout_nearly_complete_with_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v171_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_17_phase_nearly_complete_with_explicit_caveat",
            )
            self.assertEqual(
                payload["conclusion"]["v0_18_primary_phase_question"],
                "post_transition_question_exhaustion_next_honest_move",
            )
            self.assertTrue(payload["conclusion"]["explicit_caveat_present"])

    def test_invalid_when_nearly_complete_caveat_but_no_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v171_phase_ledger(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "ledger"),
            )
            build_v171_stop_condition(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "stop"),
            )
            build_v171_meaning_synthesis(
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "meaning"),
            )
            meaning_path = root / "meaning" / "summary.json"
            meaning = json.loads(meaning_path.read_text(encoding="utf-8"))
            meaning["explicit_caveat_present"] = False
            meaning["explicit_caveat_label"] = ""
            meaning["do_not_continue_v0_17_same_transition_question_loop_by_default"] = False
            meaning_path.write_text(json.dumps(meaning), encoding="utf-8")
            payload = build_v171_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(meaning_path),
                v170_closeout_path=str(paths["v170"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_17_1_handoff_phase_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
