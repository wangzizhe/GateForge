from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_4_dev_priorities import build_v0_3_4_dev_priorities


class AgentModelicaV034DevPrioritiesTests(unittest.TestCase):
    def test_build_dev_priorities_reports_top_lever_and_best_lane(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v034_dev_priorities_") as td:
            root = Path(td)
            failure_input = root / "failures.json"
            refreshed = root / "refreshed.json"
            failure_input.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "case_a",
                                "success": False,
                                "planner_invoked": True,
                                "rounds_used": 1,
                                "resolution_path": "unresolved",
                            },
                            {
                                "mutation_id": "case_b",
                                "success": False,
                                "planner_invoked": True,
                                "rounds_used": 1,
                                "resolution_path": "unresolved",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": f"cand_{idx}",
                                "holdout_clean": True,
                                "v0_3_family_id": "runtime_numerical_instability",
                                "expected_layer_hint": "layer_4",
                                "resolution_path": "llm_planner_assisted",
                                "planner_invoked": True,
                            }
                            for idx in range(5)
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_4_dev_priorities(
                failure_input_path=str(failure_input),
                refreshed_candidate_taskset_path=str(refreshed),
                out_dir=str(root / "out"),
                min_freeze_ready_cases=5,
            )
            self.assertEqual(payload["top_bottleneck_lever"]["lever"], "l2_replan")
            self.assertEqual(payload["best_harder_lane"]["family_id"], "runtime_numerical_instability")
            self.assertTrue(payload["next_actions"])


if __name__ == "__main__":
    unittest.main()
