from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_32_closeout import build_v0332_closeout
from gateforge.agent_modelica_v0_3_32_discovery_probe import build_v0332_discovery_probe
from gateforge.agent_modelica_v0_3_32_entry_spec import build_v0332_entry_spec
from gateforge.agent_modelica_v0_3_32_first_fix_evidence import build_v0332_first_fix_evidence
from gateforge.agent_modelica_v0_3_32_pipe_viability_triage import build_v0332_pipe_viability_triage


class AgentModelicaV0332PipeSliceFlowTests(unittest.TestCase):
    def _write_v0331_closeout(self, root: Path, decision: str = "stage2_medium_redeclare_discovery_coverage_partially_ready") -> None:
        (root / "v0331").mkdir(parents=True, exist_ok=True)
        (root / "v0331" / "summary.json").write_text(
            json.dumps({"conclusion": {"version_decision": decision}}),
            encoding="utf-8",
        )

    def test_pipe_viability_triage_accepts_two_patterns_in_fixture_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0331_closeout(root)
            payload = build_v0332_pipe_viability_triage(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                out_dir=str(root / "triage"),
                use_fixture_only=True,
            )
            summary = payload.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("accepted_pattern_count") or 0), 2)

    def test_entry_spec_and_first_fix_pass_in_fixture_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0331_closeout(root)
            build_v0332_pipe_viability_triage(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                out_dir=str(root / "triage"),
                use_fixture_only=True,
            )
            entry = build_v0332_entry_spec(
                triage_path=str(root / "triage" / "summary.json"),
                out_dir=str(root / "entry"),
                use_fixture_only=True,
            )
            first_fix = build_v0332_first_fix_evidence(
                entry_taskset_path=str(root / "entry" / "taskset.json"),
                out_dir=str(root / "first_fix"),
                use_fixture_only=True,
            )
            self.assertEqual((entry.get("summary") or {}).get("status"), "PASS")
            self.assertGreaterEqual(int((entry.get("summary") or {}).get("active_single_task_count") or 0), 4)
            self.assertGreaterEqual(int((entry.get("summary") or {}).get("active_dual_sidecar_count") or 0), 3)
            self.assertEqual(first_fix.get("status"), "PASS")
            self.assertEqual(first_fix.get("execution_status"), "executed")
            self.assertGreaterEqual(float(first_fix.get("signature_advance_rate_pct") or 0.0), 50.0)

    def test_discovery_and_closeout_reach_discovery_ready_in_fixture_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0331_closeout(root)
            build_v0332_pipe_viability_triage(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                out_dir=str(root / "triage"),
                use_fixture_only=True,
            )
            build_v0332_entry_spec(
                triage_path=str(root / "triage" / "summary.json"),
                out_dir=str(root / "entry"),
                use_fixture_only=True,
            )
            build_v0332_first_fix_evidence(
                entry_taskset_path=str(root / "entry" / "taskset.json"),
                out_dir=str(root / "first_fix"),
                use_fixture_only=True,
            )
            discovery = build_v0332_discovery_probe(
                first_fix_path=str(root / "first_fix" / "summary.json"),
                entry_taskset_path=str(root / "entry" / "taskset.json"),
                out_dir=str(root / "discovery"),
                use_fixture_only=True,
            )
            payload = build_v0332_closeout(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                triage_path=str(root / "triage" / "summary.json"),
                entry_spec_path=str(root / "entry" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                discovery_path=str(root / "discovery" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(discovery.get("status"), "PASS")
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "stage2_medium_redeclare_pipe_slice_discovery_ready")

    def test_closeout_returns_handoff_invalid_when_v0331_is_not_consumable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0331_closeout(root, decision="handoff_substrate_invalid")
            payload = build_v0332_closeout(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                triage_path=str(root / "triage" / "summary.json"),
                entry_spec_path=str(root / "entry" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                discovery_path=str(root / "discovery" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
