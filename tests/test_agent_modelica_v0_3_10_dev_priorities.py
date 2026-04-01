from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_10_dev_priorities import build_v0_3_10_dev_priorities


class AgentModelicaV0310DevPrioritiesTests(unittest.TestCase):
    def test_promotes_narrower_replacement_hypothesis_from_block_b(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lane = root / "lane.json"
            lane.write_text(json.dumps({"lane_status": "NEEDS_MORE_GENERATION", "admitted_count": 3}), encoding="utf-8")
            decision = root / "decision.json"
            decision.write_text(
                json.dumps({"decision": "narrower_replacement_hypothesis_supported", "replacement_hypothesis": "same_branch_one_shot_or_accidental_success"}),
                encoding="utf-8",
            )
            payload = build_v0_3_10_dev_priorities(
                lane_summary_path=str(lane),
                block_b_decision_summary_path=str(decision),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["next_hypothesis"]["lever"], "same_branch_one_shot_or_accidental_success")


if __name__ == "__main__":
    unittest.main()
