from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_8_0_closeout import build_v080_closeout
from gateforge.agent_modelica_v0_8_0_handoff_integrity import build_v080_handoff_integrity
from gateforge.agent_modelica_v0_8_0_pilot_workflow_profile import build_v080_pilot_workflow_profile
from gateforge.agent_modelica_v0_8_0_workflow_proximal_substrate import (
    build_v080_workflow_proximal_substrate,
)
from gateforge.agent_modelica_v0_8_0_workflow_substrate_admission import (
    build_v080_workflow_substrate_admission,
)


class AgentModelicaV080WorkflowProximalSubstrateFlowTests(unittest.TestCase):
    def _write_v077(self, root: Path, *, invalid: bool = False) -> None:
        payload = {
            "conclusion": {
                "version_decision": "v0_7_phase_complete_prepare_v0_8"
                if not invalid
                else "v0_7_phase_nearly_complete_with_explicit_caveat",
                "phase_status": "complete" if not invalid else "nearly_complete",
                "v0_8_handoff_spec": {
                    "v0_8_primary_phase_question": "workflow_proximal_readiness_evaluation"
                },
                "do_not_continue_v0_7_same_logic_refinement_by_default": True,
            }
        }
        (root / "v077.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_v080_reaches_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v077(root)
            build_v080_handoff_integrity(
                v077_closeout_path=str(root / "v077.json"),
                out_dir=str(root / "integrity"),
            )
            build_v080_workflow_proximal_substrate(out_dir=str(root / "substrate"))
            build_v080_pilot_workflow_profile(
                substrate_path=str(root / "substrate" / "summary.json"),
                out_dir=str(root / "pilot"),
            )
            build_v080_workflow_substrate_admission(
                substrate_path=str(root / "substrate" / "summary.json"),
                pilot_profile_path=str(root / "pilot" / "summary.json"),
                out_dir=str(root / "admission"),
            )
            payload = build_v080_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                pilot_profile_path=str(root / "pilot" / "summary.json"),
                admission_path=str(root / "admission" / "summary.json"),
                v077_closeout_path=str(root / "v077.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_8_0_workflow_proximal_substrate_ready",
            )
            self.assertTrue(
                bool((payload.get("conclusion") or {}).get("goal_level_success_definition_frozen"))
            )
            pilot = payload.get("pilot_workflow_profile") or {}
            self.assertEqual(pilot.get("execution_source"), "gateforge_agent_mock_execution_path")
            self.assertEqual(int(pilot.get("live_executor_invocation_count") or 0), 10)
            first_case = (pilot.get("case_result_table") or [])[0]
            self.assertIn("acceptance_check_results", first_case)

    def test_v080_partial_when_goal_context_signal_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v077(root)
            build_v080_handoff_integrity(
                v077_closeout_path=str(root / "v077.json"),
                out_dir=str(root / "integrity"),
            )
            build_v080_workflow_proximal_substrate(out_dir=str(root / "substrate"))
            pilot = build_v080_pilot_workflow_profile(
                substrate_path=str(root / "substrate" / "summary.json"),
                out_dir=str(root / "pilot"),
            )
            pilot["workflow_resolution_rate_requires_goal_context"] = False
            (root / "pilot" / "summary.json").write_text(json.dumps(pilot), encoding="utf-8")
            build_v080_workflow_substrate_admission(
                substrate_path=str(root / "substrate" / "summary.json"),
                pilot_profile_path=str(root / "pilot" / "summary.json"),
                out_dir=str(root / "admission"),
            )
            payload = build_v080_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                pilot_profile_path=str(root / "pilot" / "summary.json"),
                admission_path=str(root / "admission" / "summary.json"),
                v077_closeout_path=str(root / "v077.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_8_0_workflow_proximal_substrate_partial",
            )

    def test_v080_invalid_when_upstream_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v077(root, invalid=True)
            build_v080_handoff_integrity(
                v077_closeout_path=str(root / "v077.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v080_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                pilot_profile_path=str(root / "pilot" / "summary.json"),
                admission_path=str(root / "admission" / "summary.json"),
                v077_closeout_path=str(root / "v077.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_8_0_handoff_substrate_invalid",
            )


if __name__ == "__main__":
    unittest.main()
