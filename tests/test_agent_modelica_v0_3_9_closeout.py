from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_9_closeout import build_v0_3_9_closeout


class AgentModelicaV039CloseoutTests(unittest.TestCase):
    def test_closeout_accepts_replacement_hypothesis_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifests = root / "manifests.json"
            manifests.write_text(json.dumps({"metrics": {"mainline_task_count": 10, "contrast_task_count": 5}}), encoding="utf-8")
            decision = root / "decision.json"
            decision.write_text(
                json.dumps({"decision": "replacement_hypothesis_supported", "replacement_hypothesis": "single_branch_resolution_without_true_stall"}),
                encoding="utf-8",
            )
            dev = root / "dev.json"
            dev.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            verifier = root / "verifier.json"
            verifier.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text(json.dumps({"decision": "DEFER"}), encoding="utf-8")
            previous = root / "previous.json"
            previous.write_text(json.dumps({"classification": "branch_switch_behavior_forced_partial"}), encoding="utf-8")
            payload = build_v0_3_9_closeout(
                manifests_summary_path=str(manifests),
                block_b_decision_summary_path=str(decision),
                dev_priorities_summary_path=str(dev),
                verifier_summary_path=str(verifier),
                comparative_checkpoint_summary_path=str(checkpoint),
                previous_closeout_summary_path=str(previous),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["classification"], "alternative_absorption_mechanism_replaces_branch_switch")


if __name__ == "__main__":
    unittest.main()
