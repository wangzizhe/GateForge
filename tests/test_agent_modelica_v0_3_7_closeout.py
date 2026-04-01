from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_7_closeout import build_v0_3_7_closeout


class AgentModelicaV037CloseoutTests(unittest.TestCase):
    def test_build_closeout_classifies_narrowed_behavior_without_branch_signal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v037_closeout_") as td:
            root = Path(td)
            lane = root / "lane.json"
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            dev = root / "dev.json"
            verifier = root / "verifier.json"
            previous = root / "previous.json"
            lane.write_text(json.dumps({"lane_status": "CANDIDATE_READY", "admitted_count": 10}), encoding="utf-8")
            refreshed.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "planner_invoked_pct": 100.0,
                            "deterministic_only_pct": 0.0,
                        }
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "failure_bucket_counts": {
                                "success_after_branch_switch": 0,
                                "success_without_branch_switch_evidence": 10,
                                "wrong_branch_after_restore": 0,
                                "stalled_search_after_progress": 0,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            dev.write_text(json.dumps({"status": "PARTIAL"}), encoding="utf-8")
            verifier.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            previous.write_text(json.dumps({"classification": "post_restore_frontier_advanced_next_bottleneck_identified"}), encoding="utf-8")
            payload = build_v0_3_7_closeout(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                dev_priorities_summary_path=str(dev),
                verifier_summary_path=str(verifier),
                previous_closeout_summary_path=str(previous),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["classification"], "branch_switch_frontier_narrowed_behavioral_signal_missing")

    def test_build_closeout_fails_when_lane_not_candidate_ready(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v037_closeout_fail_") as td:
            root = Path(td)
            lane = root / "lane.json"
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            dev = root / "dev.json"
            verifier = root / "verifier.json"
            previous = root / "previous.json"
            lane.write_text(json.dumps({"lane_status": "NEEDS_MORE_GENERATION", "admitted_count": 3}), encoding="utf-8")
            refreshed.write_text(json.dumps({"metrics": {}}), encoding="utf-8")
            classifier.write_text(json.dumps({"metrics": {"failure_bucket_counts": {}}}), encoding="utf-8")
            dev.write_text(json.dumps({"status": "PARTIAL"}), encoding="utf-8")
            verifier.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
            previous.write_text(json.dumps({"classification": "post_restore_frontier_advanced_next_bottleneck_identified"}), encoding="utf-8")
            payload = build_v0_3_7_closeout(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                dev_priorities_summary_path=str(dev),
                verifier_summary_path=str(verifier),
                previous_closeout_summary_path=str(previous),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["classification"], "branch_switch_frontier_v0_3_7_incomplete")
