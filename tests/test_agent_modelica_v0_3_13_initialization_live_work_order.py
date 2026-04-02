from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_initialization_live_work_order import (
    build_initialization_live_work_order,
)


class AgentModelicaV0313InitializationLiveWorkOrderTests(unittest.TestCase):
    def test_summarizes_promoted_targets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            live = root / "live.json"
            live.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "task_id": "a",
                                "verdict": "PASS",
                                "progressive_solve": True,
                                "v0_3_13_source_id": "s1",
                                "v0_3_13_initialization_target_lhs": "x",
                                "rounds_used": 3,
                            },
                            {
                                "task_id": "b",
                                "verdict": "FAIL",
                                "progressive_solve": False,
                                "v0_3_13_source_id": "s2",
                                "v0_3_13_initialization_target_lhs": "y",
                                "rounds_used": 2,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_initialization_live_work_order(
                live_summary_path=str(live),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["initialization_lane_status"], "LIVE_EVIDENCE_READY")
            self.assertEqual(payload["promoted_count"], 1)
            self.assertEqual(payload["failed_count"], 1)


if __name__ == "__main__":
    unittest.main()
