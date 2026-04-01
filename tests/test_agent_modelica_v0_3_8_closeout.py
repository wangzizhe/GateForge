from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_8_closeout import build_v0_3_8_closeout


class AgentModelicaV038CloseoutTests(unittest.TestCase):
    def test_closeout_reports_forced_and_promoted_when_all_green(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files = {}
            files["lane"] = root / "lane.json"
            files["lane"].write_text(json.dumps({"lane_status": "CANDIDATE_READY"}), encoding="utf-8")
            files["refreshed"] = root / "refreshed.json"
            files["refreshed"].write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 10,
                            "successful_case_count": 5,
                            "deterministic_only_pct": 0.0,
                            "planner_invoked_pct": 100.0,
                            "success_without_branch_switch_evidence_pct": 20.0,
                            "branch_switch_evidenced_success_pct": 60.0,
                            "stall_event_observed_count": 4,
                            "success_after_branch_switch_count": 3,
                        }
                    }
                ),
                encoding="utf-8",
            )
            files["classifier"] = root / "classifier.json"
            files["classifier"].write_text(
                json.dumps({"metrics": {"failure_bucket_counts": {"success_after_branch_switch": 3, "success_without_branch_switch_evidence": 2}}}),
                encoding="utf-8",
            )
            files["dev"] = root / "dev.json"
            files["dev"].write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            files["verifier"] = root / "verifier.json"
            files["verifier"].write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            files["checkpoint"] = root / "checkpoint.json"
            files["checkpoint"].write_text(json.dumps({"decision": "DEFER"}), encoding="utf-8")
            files["previous"] = root / "previous.json"
            files["previous"].write_text(json.dumps({"classification": "branch_switch_frontier_narrowed_behavioral_signal_missing"}), encoding="utf-8")
            payload = build_v0_3_8_closeout(
                lane_summary_path=str(files["lane"]),
                refreshed_summary_path=str(files["refreshed"]),
                classifier_summary_path=str(files["classifier"]),
                dev_priorities_summary_path=str(files["dev"]),
                verifier_summary_path=str(files["verifier"]),
                comparative_checkpoint_summary_path=str(files["checkpoint"]),
                previous_closeout_summary_path=str(files["previous"]),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["classification"], "branch_switch_behavior_forced_and_promoted")

    def test_closeout_reports_partial_when_switch_signal_exists_but_gate_not_fully_met(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files = {}
            files["lane"] = root / "lane.json"
            files["lane"].write_text(json.dumps({"lane_status": "CANDIDATE_READY"}), encoding="utf-8")
            files["refreshed"] = root / "refreshed.json"
            files["refreshed"].write_text(
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
            files["classifier"] = root / "classifier.json"
            files["classifier"].write_text(
                json.dumps({"metrics": {"failure_bucket_counts": {"success_after_branch_switch": 5, "success_without_branch_switch_evidence": 5}}}),
                encoding="utf-8",
            )
            files["dev"] = root / "dev.json"
            files["dev"].write_text(json.dumps({"status": "PARTIAL"}), encoding="utf-8")
            files["verifier"] = root / "verifier.json"
            files["verifier"].write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            files["checkpoint"] = root / "checkpoint.json"
            files["checkpoint"].write_text(json.dumps({"decision": "DEFER"}), encoding="utf-8")
            files["previous"] = root / "previous.json"
            files["previous"].write_text(json.dumps({"classification": "branch_switch_frontier_narrowed_behavioral_signal_missing"}), encoding="utf-8")
            payload = build_v0_3_8_closeout(
                lane_summary_path=str(files["lane"]),
                refreshed_summary_path=str(files["refreshed"]),
                classifier_summary_path=str(files["classifier"]),
                dev_priorities_summary_path=str(files["dev"]),
                verifier_summary_path=str(files["verifier"]),
                comparative_checkpoint_summary_path=str(files["checkpoint"]),
                previous_closeout_summary_path=str(files["previous"]),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["classification"], "branch_switch_behavior_forced_partial")


if __name__ == "__main__":
    unittest.main()
