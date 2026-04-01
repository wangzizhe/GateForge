from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_6_dev_priorities import (
    build_v0_3_6_dev_priorities,
)


class AgentModelicaV036DevPrioritiesTests(unittest.TestCase):
    def test_build_dev_priorities_identifies_next_bottleneck(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_dev_priorities_") as td:
            root = Path(td)
            lane = root / "lane.json"
            classifier = root / "classifier.json"
            operator = root / "operator.json"
            lane.write_text(
                json.dumps(
                    {
                        "lane_summary": {
                            "lane_status": "ADMISSION_VALID",
                            "composition": {
                                "single_sweep_success_rate_pct": 30.0,
                            },
                            "threshold_checks": {
                                "harder_than_single_sweep": True,
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
                            "success_beyond_single_sweep_rate_pct": 60.0,
                            "failure_bucket_counts": {
                                "stalled_search_after_progress": 1,
                                "success_with_single_sweep_only": 3,
                                "success_beyond_single_sweep": 6,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            operator.write_text(
                json.dumps({"recommended_operator": "paired_value_collapse"}),
                encoding="utf-8",
            )
            payload = build_v0_3_6_dev_priorities(
                lane_summary_path=str(lane),
                classifier_summary_path=str(classifier),
                operator_analysis_summary_path=str(operator),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual((payload["next_bottleneck"] or {}).get("lever"), "guided_replan_after_progress")
        self.assertTrue((payload["deterministic_coverage_explanation"] or {}).get("present"))

    def test_build_dev_priorities_can_fall_back_to_coverage_explanation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_dev_priorities_cov_") as td:
            root = Path(td)
            lane = root / "lane.json"
            classifier = root / "classifier.json"
            operator = root / "operator.json"
            lane.write_text(
                json.dumps(
                    {
                        "lane_summary": {
                            "lane_status": "ADMISSION_VALID",
                            "composition": {
                                "single_sweep_success_rate_pct": 20.0,
                            },
                            "threshold_checks": {},
                        }
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "success_beyond_single_sweep_count": 0,
                            "success_beyond_single_sweep_rate_pct": 0.0,
                            "failure_bucket_counts": {},
                        }
                    }
                ),
                encoding="utf-8",
            )
            operator.write_text(json.dumps({}), encoding="utf-8")
            payload = build_v0_3_6_dev_priorities(
                lane_summary_path=str(lane),
                classifier_summary_path=str(classifier),
                operator_analysis_summary_path=str(operator),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual((payload["next_bottleneck"] or {}).get("lever"), "")
        self.assertEqual(
            (payload["deterministic_coverage_explanation"] or {}).get("single_sweep_success_rate_pct"),
            20.0,
        )


if __name__ == "__main__":
    unittest.main()
