from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_6_comparative_reopen_checkpoint import (
    build_comparative_reopen_checkpoint,
)


class AgentModelicaV036ComparativeReopenCheckpointTests(unittest.TestCase):
    def test_reopen_when_all_blocks_green(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_reopen_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            dev = root / "dev.json"
            verifier = root / "verifier.json"
            refreshed.write_text(json.dumps({"lane_summary": {"lane_status": "FREEZE_READY"}}), encoding="utf-8")
            dev.write_text(json.dumps({"status": "PASS", "next_bottleneck": {"lever": "guided_replan_after_progress"}}), encoding="utf-8")
            verifier.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            payload = build_comparative_reopen_checkpoint(
                refreshed_summary_path=str(refreshed),
                dev_priorities_summary_path=str(dev),
                verifier_summary_path=str(verifier),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "REOPEN")
        self.assertTrue(payload["reopen_comparative_work"])

    def test_defer_when_lane_not_freeze_ready(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_reopen_defer_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            dev = root / "dev.json"
            verifier = root / "verifier.json"
            refreshed.write_text(json.dumps({"lane_summary": {"lane_status": "ADMISSION_VALID"}}), encoding="utf-8")
            dev.write_text(json.dumps({"status": "PASS", "next_bottleneck": {"lever": "guided_replan_after_progress"}}), encoding="utf-8")
            verifier.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            payload = build_comparative_reopen_checkpoint(
                refreshed_summary_path=str(refreshed),
                dev_priorities_summary_path=str(dev),
                verifier_summary_path=str(verifier),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "DEFER")
        self.assertFalse(payload["reopen_comparative_work"])


if __name__ == "__main__":
    unittest.main()
