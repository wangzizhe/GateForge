from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_planner_bottleneck_analysis_v0_3_4 import (
    build_planner_bottleneck_analysis,
    recommend_bottleneck_levers,
)


class AgentModelicaPlannerBottleneckAnalysisV034Tests(unittest.TestCase):
    def test_recommend_l2_replan_for_single_round_unresolved_planner_case(self) -> None:
        row = {
            "failure_bucket": "unresolved_search",
            "planner_invoked": True,
            "planner_decisive": False,
            "rounds_used": 1,
        }
        payload = recommend_bottleneck_levers(row)
        self.assertEqual(payload["primary_lever"], "l2_replan")

    def test_recommend_l4_guided_search_for_multi_round_unresolved_case(self) -> None:
        row = {
            "failure_bucket": "unresolved_search",
            "planner_invoked": True,
            "planner_decisive": False,
            "rounds_used": 3,
        }
        payload = recommend_bottleneck_levers(row)
        self.assertEqual(payload["primary_lever"], "l4_guided_search")

    def test_recommend_rule_ordering_for_verifier_reject(self) -> None:
        row = {
            "failure_bucket": "verifier_reject",
            "planner_invoked": True,
            "check_model_pass": True,
            "simulate_pass": False,
        }
        payload = recommend_bottleneck_levers(row)
        self.assertEqual(payload["primary_lever"], "repair_rule_ordering")

    def test_build_analysis_ranks_primary_levers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v034_bottleneck_") as td:
            root = Path(td)
            classifier = root / "classifier.json"
            classifier.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "item_id": "case_a",
                                "failure_bucket": "unresolved_search",
                                "planner_invoked": True,
                                "rounds_used": 1,
                            },
                            {
                                "item_id": "case_b",
                                "failure_bucket": "unresolved_search",
                                "planner_invoked": True,
                                "rounds_used": 1,
                            },
                            {
                                "item_id": "case_c",
                                "failure_bucket": "patch_invalid",
                                "planner_invoked": True,
                                "check_model_pass": False,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_planner_bottleneck_analysis(
                failure_classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["metrics"]["focus_case_count"], 3)
            self.assertEqual(payload["metrics"]["top_primary_lever"], "l2_replan")
            self.assertEqual(payload["metrics"]["lever_case_counts"]["l2_replan"], 2)


if __name__ == "__main__":
    unittest.main()
