from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_7_dev_priorities import (
    build_v0_3_7_dev_priorities,
)


class AgentModelicaV037DevPrioritiesTests(unittest.TestCase):
    def test_build_dev_priorities_identifies_branch_switch_lever(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v037_dev_priorities_") as td:
            root = Path(td)
            lane = root / "lane.json"
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            lane.write_text(json.dumps({"lane_status": "CANDIDATE_READY"}), encoding="utf-8")
            refreshed.write_text(json.dumps({"metrics": {"planner_invoked_pct": 100.0, "deterministic_only_pct": 0.0}}), encoding="utf-8")
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "failure_bucket_counts": {
                                "wrong_branch_after_restore": 2,
                                "stalled_search_after_progress": 1,
                                "success_after_branch_switch": 0,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_7_dev_priorities(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual((payload["next_bottleneck"] or {}).get("lever"), "branch_switch_replan_after_stall")

    def test_build_dev_priorities_stays_partial_without_behavioral_signal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v037_dev_priorities_partial_") as td:
            root = Path(td)
            lane = root / "lane.json"
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            lane.write_text(json.dumps({"lane_status": "CANDIDATE_READY"}), encoding="utf-8")
            refreshed.write_text(json.dumps({"metrics": {"planner_invoked_pct": 100.0, "deterministic_only_pct": 0.0}}), encoding="utf-8")
            classifier.write_text(json.dumps({"metrics": {"failure_bucket_counts": {}}}), encoding="utf-8")
            payload = build_v0_3_7_dev_priorities(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "PARTIAL")
        self.assertEqual((payload["next_bottleneck"] or {}).get("lever"), "")


if __name__ == "__main__":
    unittest.main()
