from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_same_branch_continuity_failure_classifier_v0_3_10 import (
    build_same_branch_continuity_failure_classifier,
)


class AgentModelicaSameBranchContinuityFailureClassifierV0310Tests(unittest.TestCase):
    def test_classifies_rows_into_frozen_primary_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "a",
                                "verdict": "PASS",
                                "branch_identity_continuous": True,
                                "branch_switch_event_observed": False,
                                "same_branch_refinement_event_count": 2,
                            },
                            {
                                "task_id": "b",
                                "verdict": "PASS",
                                "branch_identity_continuous": True,
                                "branch_switch_event_observed": False,
                                "same_branch_refinement_event_count": 0,
                            },
                            {
                                "task_id": "c",
                                "verdict": "PASS",
                                "branch_identity_continuous": False,
                                "branch_switch_event_observed": True,
                                "same_branch_refinement_event_count": 1,
                            },
                            {
                                "task_id": "d",
                                "verdict": "FAIL",
                                "branch_identity_continuous": True,
                                "branch_switch_event_observed": False,
                                "same_branch_refinement_event_count": 1,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_same_branch_continuity_failure_classifier(
                refreshed_summary_path=str(refreshed),
                out_dir=str(root / "out"),
            )
            counts = payload["metrics"]["primary_bucket_counts"]
            self.assertEqual(counts["true_same_branch_multi_step_success"], 1)
            self.assertEqual(counts["same_branch_one_shot_or_accidental_success"], 1)
            self.assertEqual(counts["hidden_branch_change_misclassified_as_continuity"], 1)
            self.assertEqual(counts["stalled_unresolved_same_branch_failure"], 1)


if __name__ == "__main__":
    unittest.main()
