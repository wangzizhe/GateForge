from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_5_dev_priorities import build_v0_3_5_dev_priorities


class AgentModelicaV035DevPrioritiesTests(unittest.TestCase):
    def test_build_dev_priorities_promotes_parameter_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v035_dev_priorities_") as td:
            root = Path(td)
            lane = root / "lane_summary.json"
            run = root / "run_summary.json"
            lane.write_text(
                json.dumps(
                    {
                        "lane_status": "FREEZE_READY",
                        "admitted_count": 10,
                    }
                ),
                encoding="utf-8",
            )
            run.write_text(
                json.dumps(
                    {
                        "total": 10,
                        "passed": 10,
                        "planner_invoked_count": 10,
                        "deterministic_only_count": 0,
                        "results": [
                            {
                                "task_id": f"case_{idx}",
                                "verdict": "PASS",
                                "planner_invoked": True,
                                "rounds_used": 3,
                                "resolution_path": "rule_then_llm",
                            }
                            for idx in range(10)
                        ],
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_5_dev_priorities(
                lane_summary_path=str(lane),
                run_summary_path=str(run),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "PASS")
        self.assertEqual((payload.get("primary_repair_lever") or {}).get("lever"), "simulate_error_parameter_recovery_sweep")
        self.assertEqual((payload.get("best_harder_lane") or {}).get("family_id"), "post_restore_residual_conflict")
        self.assertTrue(any("simulate_error_parameter_recovery_sweep" in str(item) for item in payload.get("next_actions") or []))


if __name__ == "__main__":
    unittest.main()
