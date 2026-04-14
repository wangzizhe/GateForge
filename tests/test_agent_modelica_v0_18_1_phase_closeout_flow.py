from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_18_1_closeout import build_v181_closeout
from gateforge.agent_modelica_v0_18_1_handoff_integrity import build_v181_handoff_integrity
from gateforge.agent_modelica_v0_18_1_phase_closeout import build_v181_phase_closeout


def _write_v180_closeout(path: Path, *, version_decision: str = "v0_18_0_no_honest_next_move_remains", extra: dict | None = None) -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "next_honest_move_governance_status": "governance_ready",
            "governance_ready_for_runtime_execution": False,
            "minimum_completion_signal_pass": False,
            "next_move_viability_status": "not_justified",
            "next_move_governance_outcome": "no_honest_next_move_remains",
            "v0_18_1_handoff_mode": "prepare_v0_18_phase_closeout_or_stop",
        }
    }
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV181PhaseCloseoutFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v180 = root / "v180" / "summary.json"
            _write_v180_closeout(v180)
            payload = build_v181_handoff_integrity(v180_closeout_path=str(v180), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_default_closeout_needed_routes_to_phase_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v180 = root / "v180" / "summary.json"
            _write_v180_closeout(v180)
            payload = build_v181_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                phase_closeout_path=str(root / "phase" / "summary.json"),
                v180_closeout_path=str(v180),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_18_phase_nearly_complete_with_explicit_caveat")
            self.assertEqual(payload["conclusion"]["v0_19_primary_phase_question"], "post_v0_18_evidence_boundary_conclusion_or_stop")

    def test_deliberate_closeout_not_needed_routes_to_special_terminal_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v180 = root / "v180" / "summary.json"
            _write_v180_closeout(v180)
            build_v181_handoff_integrity(v180_closeout_path=str(v180), out_dir=str(root / "handoff"))
            build_v181_phase_closeout(closeout_needed=False, out_dir=str(root / "phase"))
            payload = build_v181_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                phase_closeout_path=str(root / "phase" / "summary.json"),
                v180_closeout_path=str(v180),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_18_phase_closeout_not_needed")
            self.assertEqual(payload["conclusion"]["next_primary_phase_question"], "post_v0_18_evidence_boundary_conclusion_or_stop")

    def test_invalid_when_handoff_integrity_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v180 = root / "v180" / "summary.json"
            _write_v180_closeout(v180, version_decision="v0_18_0_next_honest_move_governance_partial")
            payload = build_v181_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                phase_closeout_path=str(root / "phase" / "summary.json"),
                v180_closeout_path=str(v180),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_18_1_handoff_phase_inputs_invalid")
            self.assertEqual(payload["conclusion"]["next_primary_phase_question"], "rebuild_v0_18_1_phase_inputs_first")

    def test_invalid_when_closeout_needed_but_no_explicit_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v180 = root / "v180" / "summary.json"
            _write_v180_closeout(v180)
            build_v181_handoff_integrity(v180_closeout_path=str(v180), out_dir=str(root / "handoff"))
            build_v181_phase_closeout(closeout_needed=True, out_dir=str(root / "phase"))
            phase_path = root / "phase" / "summary.json"
            phase = json.loads(phase_path.read_text(encoding="utf-8"))
            phase["explicit_caveat_present"] = False
            phase["explicit_caveat_label"] = ""
            phase_path.write_text(json.dumps(phase), encoding="utf-8")
            payload = build_v181_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                phase_closeout_path=str(phase_path),
                v180_closeout_path=str(v180),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_18_1_handoff_phase_inputs_invalid")

    def test_invalid_when_carried_governance_outcome_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v180 = root / "v180" / "summary.json"
            _write_v180_closeout(v180, extra={"next_move_governance_outcome": "next_honest_move_governance_ready"})
            payload = build_v181_handoff_integrity(v180_closeout_path=str(v180), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
