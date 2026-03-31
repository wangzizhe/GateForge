from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_next_harder_lane_v0_3_4 import build_next_harder_lane


class AgentModelicaNextHarderLaneV034Tests(unittest.TestCase):
    def test_build_next_harder_lane_selects_top_freeze_ready_family(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v034_next_lane_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            lane_gate = root / "lane_gate.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "cand_a",
                                "holdout_clean": True,
                                "v0_3_family_id": "runtime_numerical_instability",
                                "expected_layer_hint": "layer_4",
                                "resolution_path": "llm_planner_assisted",
                                "planner_invoked": True,
                            },
                            {
                                "task_id": "cand_b",
                                "holdout_clean": True,
                                "v0_3_family_id": "runtime_numerical_instability",
                                "expected_layer_hint": "layer_4",
                                "resolution_path": "rule_then_llm",
                                "planner_invoked": True,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            lane_gate.write_text(
                json.dumps(
                    {
                        "lane_rows": [
                            {
                                "family_id": "runtime_numerical_instability",
                                "status": "FREEZE_READY",
                                "freeze_ready_count": 2,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_next_harder_lane(
                refreshed_candidate_taskset_path=str(refreshed),
                lane_gate_summary_path=str(lane_gate),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["selected_family_id"], "runtime_numerical_instability")
            self.assertEqual(payload["task_count"], 2)


if __name__ == "__main__":
    unittest.main()
