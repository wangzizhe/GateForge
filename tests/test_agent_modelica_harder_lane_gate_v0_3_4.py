from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_harder_lane_gate_v0_3_4 import build_harder_lane_gate


class AgentModelicaHarderLaneGateV034Tests(unittest.TestCase):
    def test_lane_becomes_freeze_ready_when_gate_count_met(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v034_lane_gate_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
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
            payload = build_harder_lane_gate(
                refreshed_candidate_taskset_path=str(refreshed),
                out_dir=str(root / "out"),
                min_freeze_ready_cases=5,
            )
            row = payload["lane_rows"][0]
            self.assertEqual(row["status"], "FREEZE_READY")
            self.assertEqual(row["freeze_ready_count"], 5)

    def test_lane_can_be_candidate_ready_without_attribution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v034_lane_candidate_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "cand_x",
                                "holdout_clean": True,
                                "v0_3_family_id": "hard_multiround_simulate_failure",
                                "expected_layer_hint": "layer_4",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_harder_lane_gate(
                refreshed_candidate_taskset_path=str(refreshed),
                out_dir=str(root / "out"),
                min_freeze_ready_cases=3,
            )
            row = payload["lane_rows"][0]
            self.assertEqual(row["status"], "CANDIDATE_READY")
            self.assertEqual(row["attribution_valid_count"], 0)


if __name__ == "__main__":
    unittest.main()
