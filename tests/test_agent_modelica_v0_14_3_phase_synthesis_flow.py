from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_14_3_closeout import build_v143_closeout
from gateforge.agent_modelica_v0_14_3_meaning_synthesis import build_v143_meaning_synthesis
from gateforge.agent_modelica_v0_14_3_phase_ledger import build_v143_phase_ledger
from gateforge.agent_modelica_v0_14_3_stop_condition import build_v143_stop_condition


def _write_closeout(path: Path, version_decision: str, extra: dict | None = None) -> None:
    payload = {"conclusion": {"version_decision": version_decision}}
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path, *, v141_effect_class: str = "non_material") -> dict[str, Path]:
    paths = {
        "v140": root / "v140" / "summary.json",
        "v141": root / "v141" / "summary.json",
        "v142": root / "v142" / "summary.json",
    }
    _write_closeout(
        paths["v140"],
        "v0_14_0_broader_change_governance_ready",
        {"v0_14_1_handoff_mode": "execute_first_broader_change_pack"},
    )
    v141_version_decision = (
        "v0_14_1_first_broader_change_pack_side_evidence_only"
        if v141_effect_class == "side_evidence_only"
        else "v0_14_1_first_broader_change_pack_non_material"
    )
    _write_closeout(
        paths["v141"],
        v141_version_decision,
        {
            "broader_change_effect_class": v141_effect_class,
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_14_2_handoff_mode": "determine_whether_stronger_broader_change_is_in_scope",
        },
    )
    _write_closeout(
        paths["v142"],
        "v0_14_2_stronger_broader_change_not_in_scope",
        {
            "stronger_broader_change_scope_status": "not_in_scope",
            "expected_information_gain": "marginal",
            "named_blocker_if_not_in_scope": (
                "admitted_broader_change_set_covers_available_scope_and_residual_gap_requires_broader_than_governed_change"
            ),
            "v0_14_3_handoff_mode": "prepare_v0_14_phase_synthesis",
        },
    )
    return paths


class AgentModelicaV143PhaseSynthesisFlowTests(unittest.TestCase):
    def test_phase_ledger_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v143_phase_ledger(
                v140_closeout_path=str(paths["v140"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "ready")
            self.assertTrue(payload["phase_primary_question_answered_enough_for_handoff"])

    def test_phase_ledger_pass_path_side_evidence_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root, v141_effect_class="side_evidence_only")
            payload = build_v143_phase_ledger(
                v140_closeout_path=str(paths["v140"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "ready")

    def test_phase_ledger_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v141"], "v0_14_1_first_broader_change_pack_execution_invalid")
            payload = build_v143_phase_ledger(
                v140_closeout_path=str(paths["v140"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "invalid")

    def test_stop_condition_nearly_complete_with_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v143_stop_condition(
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "nearly_complete_with_caveat")
            self.assertTrue(payload["broader_change_effect_answered"])
            self.assertTrue(payload["stronger_broader_change_scope_answered"])
            self.assertFalse(payload["same_class_reopen_required"])

    def test_synthetic_met_input_routes_to_invalid_because_future_reserved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v143_phase_ledger(
                v140_closeout_path=str(paths["v140"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "ledger"),
            )
            stop_dir = root / "stop"
            stop_dir.mkdir(parents=True, exist_ok=True)
            (stop_dir / "summary.json").write_text(
                json.dumps({"phase_stop_condition_status": "met"}),
                encoding="utf-8",
            )
            build_v143_meaning_synthesis(
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "meaning"),
            )
            payload = build_v143_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v140_closeout_path=str(paths["v140"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_14_3_handoff_phase_inputs_invalid")
            self.assertEqual(
                payload["conclusion"]["v0_15_primary_phase_question"],
                "met_path_not_yet_in_scope_for_v0_14_3",
            )

    def test_stop_condition_not_ready_for_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v142"],
                "v0_14_2_stronger_broader_change_justified",
                {"v0_14_3_handoff_mode": "execute_one_more_stronger_broader_change_pack"},
            )
            payload = build_v143_stop_condition(
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "not_ready_for_closeout")

    def test_meaning_synthesis_next_phase_selection(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v143_meaning_synthesis(
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "meaning"),
            )
            self.assertTrue(payload["explicit_caveat_present"])
            self.assertEqual(
                payload["next_primary_phase_question"],
                "post_broader_change_exhaustion_even_broader_change_evaluation",
            )
            self.assertTrue(payload["do_not_continue_v0_14_same_broader_change_refinement_by_default"])

    def test_closeout_nearly_complete_with_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v143_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v140_closeout_path=str(paths["v140"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_14_phase_nearly_complete_with_explicit_caveat",
            )
            self.assertEqual(
                payload["conclusion"]["v0_15_primary_phase_question"],
                "post_broader_change_exhaustion_even_broader_change_evaluation",
            )
            self.assertTrue(payload["conclusion"]["explicit_caveat_present"])

    def test_invalid_when_nearly_complete_caveat_but_no_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v143_phase_ledger(
                v140_closeout_path=str(paths["v140"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "ledger"),
            )
            build_v143_stop_condition(
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "stop"),
            )
            build_v143_meaning_synthesis(
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "meaning"),
            )
            meaning_path = root / "meaning" / "summary.json"
            meaning = json.loads(meaning_path.read_text(encoding="utf-8"))
            meaning["explicit_caveat_present"] = False
            meaning["explicit_caveat_label"] = ""
            meaning["do_not_continue_v0_14_same_broader_change_refinement_by_default"] = False
            meaning_path.write_text(json.dumps(meaning), encoding="utf-8")
            payload = build_v143_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(meaning_path),
                v140_closeout_path=str(paths["v140"]),
                v141_closeout_path=str(paths["v141"]),
                v142_closeout_path=str(paths["v142"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_14_3_handoff_phase_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
