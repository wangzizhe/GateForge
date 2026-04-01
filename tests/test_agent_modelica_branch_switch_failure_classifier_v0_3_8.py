from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_branch_switch_failure_classifier_v0_3_8 import (
    build_branch_switch_failure_classifier,
)


class BranchSwitchFailureClassifierV038Tests(unittest.TestCase):
    def test_classifier_assigns_primary_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            refreshed = Path(td) / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "frozen_mainline_task_ids": ["demo"],
                        "tasks": [
                            {
                                "task_id": "demo",
                                "verdict": "PASS",
                                "executor_status": "PASS",
                                "success_after_branch_switch": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_branch_switch_failure_classifier(
                refreshed_summary_path=str(refreshed),
                out_dir=str(Path(td) / "out"),
            )
            self.assertEqual(payload["metrics"]["failure_bucket_counts"]["success_after_branch_switch"], 1)
            self.assertEqual(payload["rows"][0]["branch_switch_primary_bucket"], "success_after_branch_switch")


if __name__ == "__main__":
    unittest.main()
