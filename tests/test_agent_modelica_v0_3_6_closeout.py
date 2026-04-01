from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_6_closeout import build_v0_3_6_closeout


class AgentModelicaV036CloseoutTests(unittest.TestCase):
    def test_build_closeout_classifies_next_bottleneck_identified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_closeout_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            dev = root / "dev.json"
            verifier = root / "verifier.json"
            checkpoint = root / "checkpoint.json"
            previous = root / "previous.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "lane_summary": {
                            "lane_status": "ADMISSION_VALID",
                            "admitted_count": 6,
                            "composition": {
                                "single_sweep_success_rate_pct": 30.0,
                                "first_correction_residual_count": 6,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "success_beyond_single_sweep_count": 6,
                            "failure_bucket_counts": {
                                "stalled_search_after_progress": 1,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            dev.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "next_bottleneck": {"lever": "guided_replan_after_progress"},
                        "deterministic_coverage_explanation": {"present": True},
                    }
                ),
                encoding="utf-8",
            )
            verifier.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            checkpoint.write_text(json.dumps({"status": "DEFER"}), encoding="utf-8")
            previous.write_text(json.dumps({"classification": "post_restore_frontier_advanced_parameter_recovery_promoted"}), encoding="utf-8")
            payload = build_v0_3_6_closeout(
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                dev_priorities_summary_path=str(dev),
                verifier_summary_path=str(verifier),
                comparative_checkpoint_summary_path=str(checkpoint),
                previous_closeout_summary_path=str(previous),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["classification"], "post_restore_frontier_advanced_next_bottleneck_identified")

    def test_build_closeout_fails_when_verifier_not_green(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_closeout_fail_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            dev = root / "dev.json"
            verifier = root / "verifier.json"
            checkpoint = root / "checkpoint.json"
            previous = root / "previous.json"
            refreshed.write_text(json.dumps({"lane_summary": {"lane_status": "ADMISSION_VALID"}}), encoding="utf-8")
            classifier.write_text(json.dumps({"metrics": {}}), encoding="utf-8")
            dev.write_text(json.dumps({"status": "PASS", "next_bottleneck": {"lever": "guided_replan_after_progress"}}), encoding="utf-8")
            verifier.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
            checkpoint.write_text(json.dumps({"status": "DEFER"}), encoding="utf-8")
            previous.write_text(json.dumps({"classification": "post_restore_frontier_advanced_parameter_recovery_promoted"}), encoding="utf-8")
            payload = build_v0_3_6_closeout(
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                dev_priorities_summary_path=str(dev),
                verifier_summary_path=str(verifier),
                comparative_checkpoint_summary_path=str(checkpoint),
                previous_closeout_summary_path=str(previous),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["classification"], "post_restore_frontier_v0_3_6_incomplete")


if __name__ == "__main__":
    unittest.main()
