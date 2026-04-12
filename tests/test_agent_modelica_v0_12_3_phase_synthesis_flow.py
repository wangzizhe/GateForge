from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_12_3_closeout import build_v123_closeout
from gateforge.agent_modelica_v0_12_3_meaning_synthesis import build_v123_meaning_synthesis
from gateforge.agent_modelica_v0_12_3_phase_ledger import build_v123_phase_ledger
from gateforge.agent_modelica_v0_12_3_stop_condition import build_v123_stop_condition


def _write_closeout(path: Path, version_decision: str, extra: dict | None = None) -> None:
    payload = {"conclusion": {"version_decision": version_decision}}
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v120": root / "v120" / "summary.json",
        "v121": root / "v121" / "summary.json",
        "v122": root / "v122" / "summary.json",
    }
    _write_closeout(
        paths["v120"],
        "v0_12_0_operational_remedy_governance_ready",
        {"v0_12_1_handoff_mode": "execute_first_bounded_operational_remedy_pack"},
    )
    _write_closeout(
        paths["v121"],
        "v0_12_1_first_remedy_pack_non_material",
        {
            "pack_level_effect": "non_material",
            "same_execution_source": True,
            "same_case_requirement_met": True,
            "v0_12_2_handoff_mode": "determine_whether_stronger_remedy_is_in_scope",
        },
    )
    _write_closeout(
        paths["v122"],
        "v0_12_2_stronger_bounded_remedy_not_in_scope",
        {
            "stronger_remedy_scope_status": "not_in_scope",
            "expected_information_gain": "marginal",
            "named_blocker_if_not_in_scope": (
                "residual_core_capability_gap_requires_capability_level_improvement_not_shell_hardening"
            ),
            "v0_12_3_handoff_mode": "prepare_v0_12_phase_synthesis",
        },
    )
    return paths


class AgentModelicaV123PhaseSynthesisFlowTests(unittest.TestCase):

    # ---- Test 1: phase-ledger pass path -------------------------------------

    def test_phase_ledger_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v123_phase_ledger(
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "PASS")
            self.assertTrue(payload["phase_primary_question_answered_enough_for_handoff"])

    # ---- Test 2: phase-ledger invalid path ----------------------------------

    def test_phase_ledger_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v121"], "v0_12_1_first_remedy_pack_side_evidence_only")
            payload = build_v123_phase_ledger(
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "FAIL")

    # ---- Test 3: stop-condition nearly_complete_with_caveat -----------------

    def test_stop_condition_nearly_complete_with_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v123_stop_condition(
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "nearly_complete_with_caveat")
            self.assertTrue(payload["bounded_operational_remedy_effect_answered"])
            self.assertTrue(payload["stronger_bounded_remedy_scope_answered"])
            self.assertFalse(payload["same_class_reopen_required"])

    # ---- Test 4: synthetic met input routes to invalid ----------------------

    def test_synthetic_met_input_routes_to_invalid_because_future_reserved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v123_phase_ledger(
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "ledger"),
            )
            # Patch stop condition file to synthetic met
            stop_dir = root / "stop"
            stop_dir.mkdir(parents=True, exist_ok=True)
            (stop_dir / "summary.json").write_text(
                json.dumps({"phase_stop_condition_status": "met"}),
                encoding="utf-8",
            )
            build_v123_meaning_synthesis(
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "meaning"),
            )
            payload = build_v123_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_12_3_handoff_phase_inputs_invalid")
            self.assertEqual(
                payload["conclusion"]["v0_13_primary_phase_question"],
                "met_path_not_yet_in_scope_for_v0_12_3",
            )

    # ---- Test 5: stop-condition not_ready_for_closeout ----------------------

    def test_stop_condition_not_ready_for_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            # Break v0.12.2 so stronger_bounded_remedy_scope_answered = false
            _write_closeout(
                paths["v122"],
                "v0_12_2_stronger_bounded_remedy_justified",
                {"v0_12_3_handoff_mode": "execute_stronger_bounded_operational_remedy"},
            )
            payload = build_v123_stop_condition(
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "not_ready_for_closeout")

    # ---- Test 6: meaning-synthesis next-phase selection ---------------------

    def test_meaning_synthesis_next_phase_selection(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v123_meaning_synthesis(
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "meaning"),
            )
            self.assertTrue(payload["explicit_caveat_present"])
            self.assertEqual(
                payload["next_primary_phase_question"],
                "capability_level_improvement_evaluation_after_operational_remedy_exhaustion",
            )
            self.assertTrue(payload["do_not_continue_v0_12_same_operational_remedy_refinement_by_default"])

    # ---- Test 7: valid phase closeout to nearly_complete_with_explicit_caveat

    def test_closeout_nearly_complete_with_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v123_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_12_phase_nearly_complete_with_explicit_caveat",
            )
            self.assertEqual(
                payload["conclusion"]["v0_13_primary_phase_question"],
                "capability_level_improvement_evaluation_after_operational_remedy_exhaustion",
            )
            self.assertTrue(payload["conclusion"]["explicit_caveat_present"])

    # ---- Test 8: invalid when nearly_complete_with_caveat + explicit_caveat_present = false

    def test_invalid_when_nearly_complete_caveat_but_no_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v123_phase_ledger(
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "ledger"),
            )
            build_v123_stop_condition(
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "stop"),
            )
            build_v123_meaning_synthesis(
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "meaning"),
            )
            # Patch meaning synthesis to remove explicit caveat
            meaning_path = root / "meaning" / "summary.json"
            meaning = json.loads(meaning_path.read_text(encoding="utf-8"))
            meaning["explicit_caveat_present"] = False
            meaning["explicit_caveat_label"] = ""
            meaning["do_not_continue_v0_12_same_operational_remedy_refinement_by_default"] = False
            meaning_path.write_text(json.dumps(meaning), encoding="utf-8")
            payload = build_v123_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(meaning_path),
                v120_closeout_path=str(paths["v120"]),
                v121_closeout_path=str(paths["v121"]),
                v122_closeout_path=str(paths["v122"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_12_3_handoff_phase_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
