from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_11_7_closeout import build_v117_closeout
from gateforge.agent_modelica_v0_11_7_meaning_synthesis import build_v117_meaning_synthesis
from gateforge.agent_modelica_v0_11_7_phase_ledger import build_v117_phase_ledger
from gateforge.agent_modelica_v0_11_7_stop_condition import build_v117_stop_condition


def _write_closeout(path: Path, version_decision: str, extra: dict | None = None) -> None:
    payload = {"conclusion": {"version_decision": version_decision}}
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v110": root / "v110" / "summary.json",
        "v111": root / "v111" / "summary.json",
        "v112": root / "v112" / "summary.json",
        "v113": root / "v113" / "summary.json",
        "v114": root / "v114" / "summary.json",
        "v115": root / "v115" / "summary.json",
        "v116": root / "v116" / "summary.json",
    }
    _write_closeout(
        paths["v110"],
        "v0_11_0_product_gap_governance_ready",
        {"v0_11_1_handoff_mode": "execute_first_product_gap_patch_pack"},
    )
    _write_closeout(
        paths["v111"],
        "v0_11_1_first_product_gap_patch_pack_ready",
        {"v0_11_2_handoff_mode": "freeze_first_product_gap_evaluation_substrate"},
    )
    _write_closeout(
        paths["v112"],
        "v0_11_2_first_product_gap_substrate_ready",
        {"v0_11_3_handoff_mode": "characterize_first_product_gap_profile"},
    )
    _write_closeout(
        paths["v113"],
        "v0_11_3_first_product_gap_profile_characterized",
        {"v0_11_4_handoff_mode": "freeze_first_product_gap_thresholds"},
    )
    _write_closeout(
        paths["v114"],
        "v0_11_4_first_product_gap_thresholds_frozen",
        {"v0_11_5_handoff_mode": "adjudicate_first_product_gap_profile_against_frozen_thresholds"},
    )
    _write_closeout(
        paths["v115"],
        "v0_11_5_first_product_gap_profile_partial_but_interpretable",
        {
            "formal_adjudication_label": "product_gap_partial_but_interpretable",
            "dominant_gap_family_readout": "residual_core_capability_gap",
            "v0_11_6_handoff_mode": "decide_whether_one_more_bounded_product_gap_step_is_still_worth_it",
        },
    )
    _write_closeout(
        paths["v116"],
        "v0_11_6_more_bounded_product_gap_step_not_worth_it",
        {
            "remaining_uncertainty_status": "no_phase_relevant_uncertainty_remaining",
            "expected_information_gain": "marginal",
            "proposed_next_step_kind": "none",
            "v0_11_7_handoff_mode": "prepare_v0_11_phase_synthesis",
        },
    )
    return paths


class AgentModelicaV117PhaseSynthesisFlowTests(unittest.TestCase):
    def test_phase_ledger_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v117_phase_ledger(
                v110_closeout_path=str(paths["v110"]),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v113_closeout_path=str(paths["v113"]),
                v114_closeout_path=str(paths["v114"]),
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "PASS")

    def test_phase_ledger_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v114"], "v0_11_4_first_product_gap_thresholds_partial")
            payload = build_v117_phase_ledger(
                v110_closeout_path=str(paths["v110"]),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v113_closeout_path=str(paths["v113"]),
                v114_closeout_path=str(paths["v114"]),
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["phase_ledger_status"], "FAIL")

    def test_stop_condition_nearly_complete_with_caveat_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v117_stop_condition(
                v110_closeout_path=str(paths["v110"]),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v113_closeout_path=str(paths["v113"]),
                v114_closeout_path=str(paths["v114"]),
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "nearly_complete_with_caveat")

    def test_synthetic_met_input_correctly_routes_to_invalid_because_not_in_scope(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v115"],
                "v0_11_5_first_product_gap_profile_partial_but_interpretable",
                {
                    "formal_adjudication_label": "product_gap_supported",
                    "dominant_gap_family_readout": "residual_core_capability_gap",
                    "v0_11_6_handoff_mode": "decide_whether_one_more_bounded_product_gap_step_is_still_worth_it",
                },
            )
            payload = build_v117_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v110_closeout_path=str(paths["v110"]),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v113_closeout_path=str(paths["v113"]),
                v114_closeout_path=str(paths["v114"]),
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_7_handoff_phase_inputs_invalid")

    def test_stop_condition_not_ready_for_closeout_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v113"], "v0_11_3_first_product_gap_profile_partial")
            payload = build_v117_stop_condition(
                v110_closeout_path=str(paths["v110"]),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v113_closeout_path=str(paths["v113"]),
                v114_closeout_path=str(paths["v114"]),
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "not_ready_for_closeout")

    def test_meaning_synthesis_next_phase_selection(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v117_meaning_synthesis(
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "meaning"),
            )
            self.assertTrue(payload["explicit_caveat_present"])
            self.assertEqual(
                payload["next_primary_phase_question"],
                "workflow_to_product_gap_operational_remedy_evaluation",
            )

    def test_closeout_nearly_complete_with_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v117_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v110_closeout_path=str(paths["v110"]),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v113_closeout_path=str(paths["v113"]),
                v114_closeout_path=str(paths["v114"]),
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_phase_nearly_complete_with_explicit_caveat")
            self.assertEqual(
                payload["conclusion"]["v0_12_primary_phase_question"],
                "workflow_to_product_gap_operational_remedy_evaluation",
            )

    def test_explicit_invalid_edge_case_when_nearly_complete_with_caveat_has_no_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v117_phase_ledger(
                v110_closeout_path=str(paths["v110"]),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v113_closeout_path=str(paths["v113"]),
                v114_closeout_path=str(paths["v114"]),
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "ledger"),
            )
            build_v117_stop_condition(
                v110_closeout_path=str(paths["v110"]),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v113_closeout_path=str(paths["v113"]),
                v114_closeout_path=str(paths["v114"]),
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "stop"),
            )
            build_v117_meaning_synthesis(
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "meaning"),
            )
            meaning_path = root / "meaning" / "summary.json"
            meaning = json.loads(meaning_path.read_text(encoding="utf-8"))
            meaning["explicit_caveat_present"] = False
            meaning["explicit_caveat_label"] = ""
            meaning_path.write_text(json.dumps(meaning), encoding="utf-8")
            payload = build_v117_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(meaning_path),
                v110_closeout_path=str(paths["v110"]),
                v111_closeout_path=str(paths["v111"]),
                v112_closeout_path=str(paths["v112"]),
                v113_closeout_path=str(paths["v113"]),
                v114_closeout_path=str(paths["v114"]),
                v115_closeout_path=str(paths["v115"]),
                v116_closeout_path=str(paths["v116"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_7_handoff_phase_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
