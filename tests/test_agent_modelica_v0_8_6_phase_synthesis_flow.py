from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_8_6_closeout import build_v086_closeout
from gateforge.agent_modelica_v0_8_6_meaning_synthesis import build_v086_meaning_synthesis
from gateforge.agent_modelica_v0_8_6_phase_ledger import build_v086_phase_ledger
from gateforge.agent_modelica_v0_8_6_stop_condition import build_v086_stop_condition


def _write_closeout(path: Path, version_decision: str, extra: dict | None = None) -> None:
    payload = {"conclusion": {"version_decision": version_decision}}
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v080": root / "v080" / "summary.json",
        "v081": root / "v081" / "summary.json",
        "v082": root / "v082" / "summary.json",
        "v083": root / "v083" / "summary.json",
        "v084": root / "v084" / "summary.json",
        "v085": root / "v085" / "summary.json",
    }
    _write_closeout(paths["v080"], "v0_8_0_workflow_proximal_substrate_ready")
    _write_closeout(paths["v081"], "v0_8_1_workflow_readiness_profile_characterized")
    _write_closeout(paths["v082"], "v0_8_2_workflow_readiness_thresholds_frozen")
    _write_closeout(paths["v083"], "v0_8_3_threshold_pack_validated")
    _write_closeout(
        paths["v084"],
        "v0_8_4_workflow_readiness_partial_but_interpretable",
        {
            "adjudication_route": "workflow_readiness_partial_but_interpretable",
            "adjudication_route_count": 1,
            "legacy_bucket_sidecar_still_interpretable": True,
        },
    )
    _write_closeout(
        paths["v085"],
        "v0_8_5_same_logic_refinement_not_worth_it",
        {
            "v0_8_6_handoff_mode": "prepare_v0_8_phase_closeout",
            "remaining_gap_status": "no_same_logic_gap_with_meaningful_expected_gain",
            "remaining_gap_is_threshold_proximal": False,
            "remaining_gap_is_same_logic_addressable": False,
        },
    )
    return paths


class AgentModelicaV086PhaseSynthesisFlowTests(unittest.TestCase):
    def test_phase_ledger_passes_with_correct_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v086_phase_ledger(
                v080_closeout_path=str(paths["v080"]),
                v081_closeout_path=str(paths["v081"]),
                v082_closeout_path=str(paths["v082"]),
                v083_closeout_path=str(paths["v083"]),
                v084_closeout_path=str(paths["v084"]),
                v085_closeout_path=str(paths["v085"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["status"], "PASS")

    def test_stop_condition_met_with_standard_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v086_stop_condition(
                v080_closeout_path=str(paths["v080"]),
                v081_closeout_path=str(paths["v081"]),
                v082_closeout_path=str(paths["v082"]),
                v083_closeout_path=str(paths["v083"]),
                v084_closeout_path=str(paths["v084"]),
                v085_closeout_path=str(paths["v085"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "met")

    def test_meaning_synthesis_selects_barrier_aware_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v086_meaning_synthesis(
                v084_closeout_path=str(paths["v084"]),
                v085_closeout_path=str(paths["v085"]),
                out_dir=str(root / "meaning"),
            )
            self.assertTrue(payload["explicit_caveat_present"])
            self.assertEqual(
                payload["v0_9_primary_phase_question"],
                "authenticity_constrained_barrier_aware_workflow_expansion",
            )

    def test_closeout_reaches_nearly_complete_with_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v086_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v080_closeout_path=str(paths["v080"]),
                v081_closeout_path=str(paths["v081"]),
                v082_closeout_path=str(paths["v082"]),
                v083_closeout_path=str(paths["v083"]),
                v084_closeout_path=str(paths["v084"]),
                v085_closeout_path=str(paths["v085"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_phase_nearly_complete_with_explicit_caveat",
            )
            self.assertEqual(
                payload["conclusion"]["v0_9_primary_phase_question"],
                "authenticity_constrained_barrier_aware_workflow_expansion",
            )
            self.assertTrue(payload["conclusion"]["do_not_continue_v0_8_same_logic_refinement_by_default"])

    def test_closeout_returns_invalid_on_bad_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v083"], "v0_8_3_threshold_pack_partial")
            payload = build_v086_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v080_closeout_path=str(paths["v080"]),
                v081_closeout_path=str(paths["v081"]),
                v082_closeout_path=str(paths["v082"]),
                v083_closeout_path=str(paths["v083"]),
                v084_closeout_path=str(paths["v084"]),
                v085_closeout_path=str(paths["v085"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_6_handoff_phase_inputs_invalid",
            )


if __name__ == "__main__":
    unittest.main()
