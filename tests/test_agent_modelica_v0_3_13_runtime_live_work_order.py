from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_runtime_live_work_order import (
    build_runtime_live_work_order,
)


class AgentModelicaV0313RuntimeLiveWorkOrderTests(unittest.TestCase):
    def test_builds_promoted_and_failed_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            summary = root / "live.json"
            summary.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "task_id": "a",
                                "verdict": "PASS",
                                "progressive_solve": True,
                                "v0_3_13_source_task_id": "seed_a",
                                "v0_3_13_candidate_pair": ["R", "C"],
                                "resolution_path": "rule_then_llm",
                                "rounds_used": 3,
                            },
                            {
                                "task_id": "b",
                                "verdict": "FAIL",
                                "progressive_solve": False,
                                "v0_3_13_source_task_id": "seed_b",
                                "v0_3_13_candidate_pair": ["m", "k"],
                                "resolution_path": "unresolved",
                                "rounds_used": 2,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_runtime_live_work_order(
                live_summary_path=str(summary),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["runtime_lane_status"], "LIVE_EVIDENCE_READY")
            self.assertEqual(payload["promoted_pair_count"], 1)
            self.assertEqual(payload["failed_pair_count"], 1)
            self.assertEqual(payload["promoted_pairs"][0]["candidate_pair"], ["R", "C"])


if __name__ == "__main__":
    unittest.main()
