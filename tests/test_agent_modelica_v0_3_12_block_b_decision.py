from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_12_block_b_decision import (
    build_v0_3_12_block_b_decision,
)


class AgentModelicaV0312BlockBDecisionTests(unittest.TestCase):
    def test_confirms_one_shot_when_true_continuity_pct_is_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lane = root / "lane.json"
            lane.write_text(
                json.dumps({"lane_status": "CANDIDATE_READY", "admitted_count": 8}),
                encoding="utf-8",
            )
            classifier = root / "classifier.json"
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "successful_case_count": 8,
                            "successful_labeled_count": 6,
                            "unknown_success_pct": 0.0,
                            "true_continuity_count": 1,
                            "true_continuity_pct": 16.7,
                            "successful_label_counts": {
                                "one_shot": 4,
                                "true_continuity": 1,
                                "multi_step_non_continuity": 1,
                                "unknown": 0,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_12_block_b_decision(
                lane_summary_path=str(lane),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["decision"], "one_shot_hypothesis_confirmed")

    def test_returns_signal_too_sparse_when_unknown_rate_exceeds_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lane = root / "lane.json"
            lane.write_text(
                json.dumps({"lane_status": "CANDIDATE_READY", "admitted_count": 8}),
                encoding="utf-8",
            )
            classifier = root / "classifier.json"
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "successful_case_count": 8,
                            "successful_labeled_count": 5,
                            "unknown_success_pct": 37.5,
                            "true_continuity_count": 1,
                            "true_continuity_pct": 20.0,
                            "successful_label_counts": {
                                "one_shot": 2,
                                "true_continuity": 1,
                                "multi_step_non_continuity": 2,
                                "unknown": 3,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_12_block_b_decision(
                lane_summary_path=str(lane),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["decision"], "inconclusive_signal_too_sparse")


if __name__ == "__main__":
    unittest.main()
