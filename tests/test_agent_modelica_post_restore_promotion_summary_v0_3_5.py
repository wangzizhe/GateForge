from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_post_restore_promotion_summary_v0_3_5 import (
    build_post_restore_promotion_summary,
)


class AgentModelicaPostRestorePromotionSummaryV035Tests(unittest.TestCase):
    def test_build_post_restore_promotion_summary_marks_promotion_ready(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v035_post_restore_promotion_") as td:
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
            summary = build_post_restore_promotion_summary(
                lane_summary_path=str(lane),
                run_summary_path=str(run),
                out_dir=str(root / "out"),
            )
        self.assertEqual(summary.get("status"), "PROMOTION_READY")
        self.assertTrue((summary.get("decision") or {}).get("promote"))
        self.assertEqual((summary.get("observed_metrics") or {}).get("rule_then_llm_count"), 10)


if __name__ == "__main__":
    unittest.main()
