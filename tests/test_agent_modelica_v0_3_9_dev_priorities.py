from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_9_dev_priorities import build_v0_3_9_dev_priorities


class AgentModelicaV039DevPrioritiesTests(unittest.TestCase):
    def test_promotes_replacement_hypothesis_when_block_b_supports_it(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifests = root / "manifests.json"
            manifests.write_text(json.dumps({"metrics": {"mainline_task_count": 10, "contrast_task_count": 5, "explicit_branch_switch_subset_count": 5}}), encoding="utf-8")
            decision = root / "decision.json"
            decision.write_text(
                json.dumps({"decision": "replacement_hypothesis_supported", "replacement_hypothesis": "single_branch_resolution_without_true_stall"}),
                encoding="utf-8",
            )
            payload = build_v0_3_9_dev_priorities(
                manifests_summary_path=str(manifests),
                block_b_decision_summary_path=str(decision),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["next_hypothesis"]["lever"], "single_branch_resolution_without_true_stall")


if __name__ == "__main__":
    unittest.main()
