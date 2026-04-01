from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_6_block_a_operator_analysis import (
    build_block_a_operator_analysis,
)


class AgentModelicaV036BlockAOperatorAnalysisTests(unittest.TestCase):
    def test_recommends_operator_with_planner_usage_and_low_deterministic_rate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v036_op_analysis_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "a1",
                                "hidden_base_operator": "paired_value_collapse",
                                "planner_invoked": True,
                                "resolution_path": "rule_then_llm",
                                "rounds_used": 4,
                            },
                            {
                                "task_id": "a2",
                                "hidden_base_operator": "paired_value_collapse",
                                "planner_invoked": True,
                                "resolution_path": "rule_then_llm",
                                "rounds_used": 3,
                            },
                            {
                                "task_id": "b1",
                                "hidden_base_operator": "paired_value_bias_shift",
                                "planner_invoked": False,
                                "resolution_path": "deterministic_rule_only",
                                "rounds_used": 1,
                            },
                            {
                                "task_id": "b2",
                                "hidden_base_operator": "paired_value_bias_shift",
                                "planner_invoked": False,
                                "resolution_path": "deterministic_rule_only",
                                "rounds_used": 1,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_block_a_operator_analysis(
                refreshed_summary_path=str(refreshed),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["recommended_operator"], "paired_value_collapse")
            rows = {row["hidden_base_operator"]: row for row in payload["operator_rows"]}
            self.assertEqual(rows["paired_value_collapse"]["planner_invoked_pct"], 100.0)
            self.assertEqual(rows["paired_value_bias_shift"]["deterministic_only_pct"], 100.0)
            self.assertTrue(rows["paired_value_collapse"]["promising_harder_direction"])
            self.assertFalse(rows["paired_value_bias_shift"]["promising_harder_direction"])
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
