from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_10_closeout import build_v0_3_10_closeout


class AgentModelicaV0310CloseoutTests(unittest.TestCase):
    def test_closeout_accepts_narrowed_small_lane_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lane = root / "lane.json"
            lane.write_text(json.dumps({"lane_status": "NEEDS_MORE_GENERATION", "admitted_count": 3}), encoding="utf-8")
            refreshed = root / "refreshed.json"
            refreshed.write_text(json.dumps({"metrics": {"total_rows": 3, "success_after_same_branch_continuation_count": 0}}), encoding="utf-8")
            classifier = root / "classifier.json"
            classifier.write_text(json.dumps({"metrics": {"total_rows": 3}}), encoding="utf-8")
            decision = root / "decision.json"
            decision.write_text(
                json.dumps({"decision": "narrower_replacement_hypothesis_supported", "replacement_hypothesis": "same_branch_one_shot_or_accidental_success"}),
                encoding="utf-8",
            )
            dev = root / "dev.json"
            dev.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            verifier = root / "verifier.json"
            verifier.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text(json.dumps({"decision": "DEFER"}), encoding="utf-8")
            previous = root / "previous.json"
            previous.write_text(json.dumps({"classification": "alternative_absorption_mechanism_replaces_branch_switch"}), encoding="utf-8")
            payload = build_v0_3_10_closeout(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                block_b_decision_summary_path=str(decision),
                dev_priorities_summary_path=str(dev),
                verifier_summary_path=str(verifier),
                comparative_checkpoint_summary_path=str(checkpoint),
                previous_closeout_summary_path=str(previous),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["classification"], "same_branch_continuity_narrowed_on_small_lane")


if __name__ == "__main__":
    unittest.main()
