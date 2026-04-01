from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_same_branch_continuity_taskset_v0_3_10 import (
    build_same_branch_continuity_taskset,
)


class AgentModelicaSameBranchContinuityTasksetV0310Tests(unittest.TestCase):
    def test_builds_taskset_from_v039_absorbed_success_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "classifier.json"
            source.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "task_id": "keep_me",
                                "absorbed_success_primary_bucket": "single_branch_resolution_without_true_stall",
                                "selected_branch": "continue_on_m",
                                "current_branch": "continue_on_m",
                                "detected_branch_sequence": ["continue_on_m"],
                                "candidate_next_branches": [{"branch_id": "continue_on_m"}],
                            },
                            {
                                "task_id": "skip_me",
                                "absorbed_success_primary_bucket": "noncontributing_branch_sequence",
                                "selected_branch": "continue_on_x",
                                "current_branch": "continue_on_x",
                                "detected_branch_sequence": ["continue_on_x"],
                                "candidate_next_branches": [{"branch_id": "continue_on_x"}],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_same_branch_continuity_taskset(
                source_classifier_summary_path=str(source),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["task_count"], 1)
            self.assertEqual(payload["task_ids"], ["keep_me"])


if __name__ == "__main__":
    unittest.main()
