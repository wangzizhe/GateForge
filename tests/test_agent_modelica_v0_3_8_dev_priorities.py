from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_8_dev_priorities import build_v0_3_8_dev_priorities


class AgentModelicaV038DevPrioritiesTests(unittest.TestCase):
    def test_build_priorities_promotes_branch_switch_when_gates_and_counts_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lane = root / "lane.json"
            lane.write_text(json.dumps({"family_id": "post_restore_explicit_branch_switch_after_stall", "lane_status": "CANDIDATE_READY"}), encoding="utf-8")
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 10,
                            "successful_case_count": 5,
                            "deterministic_only_pct": 0.0,
                            "planner_invoked_pct": 100.0,
                            "success_without_branch_switch_evidence_pct": 30.0,
                            "branch_switch_evidenced_success_pct": 40.0,
                            "stall_event_observed_count": 3,
                            "success_after_branch_switch_count": 3,
                        }
                    }
                ),
                encoding="utf-8",
            )
            classifier = root / "classifier.json"
            classifier.write_text(
                json.dumps({"metrics": {"failure_bucket_counts": {"success_after_branch_switch": 3, "success_without_branch_switch_evidence": 2}}}),
                encoding="utf-8",
            )
            payload = build_v0_3_8_dev_priorities(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["next_bottleneck"]["lever"], "branch_switch_replan_after_stall")

    def test_build_priorities_marks_partial_when_switch_signal_present_but_not_dominant(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lane = root / "lane.json"
            lane.write_text(json.dumps({"family_id": "post_restore_explicit_branch_switch_after_stall", "lane_status": "CANDIDATE_READY"}), encoding="utf-8")
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 10,
                            "successful_case_count": 10,
                            "deterministic_only_pct": 0.0,
                            "planner_invoked_pct": 100.0,
                            "success_without_branch_switch_evidence_pct": 50.0,
                            "branch_switch_evidenced_success_pct": 50.0,
                            "stall_event_observed_count": 6,
                            "success_after_branch_switch_count": 5,
                        }
                    }
                ),
                encoding="utf-8",
            )
            classifier = root / "classifier.json"
            classifier.write_text(
                json.dumps({"metrics": {"failure_bucket_counts": {"success_after_branch_switch": 5, "success_without_branch_switch_evidence": 5}}}),
                encoding="utf-8",
            )
            payload = build_v0_3_8_dev_priorities(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "PARTIAL")
            self.assertEqual(payload["next_bottleneck"]["lever"], "branch_switch_replan_after_stall")
            self.assertEqual(payload["next_bottleneck"]["reason"], "explicit_branch_switch_signal_present_but_not_dominant")


if __name__ == "__main__":
    unittest.main()
