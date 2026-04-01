from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_9_absorbed_success_classifier import (
    build_v0_3_9_absorbed_success_classifier,
)


class AgentModelicaV039AbsorbedSuccessClassifierTests(unittest.TestCase):
    def test_classifies_absorbed_rows_into_mutually_exclusive_primary_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "contrast.json"
            manifest.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "single",
                                "success_without_branch_switch_evidence": True,
                                "detected_branch_sequence": ["continue_on_R"],
                                "stall_event_observed": False,
                            },
                            {
                                "task_id": "multi",
                                "success_without_branch_switch_evidence": True,
                                "detected_branch_sequence": ["switch_to_R", "continue_on_A"],
                                "stall_event_observed": True,
                                "success_after_branch_switch": False,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_9_absorbed_success_classifier(
                contrast_manifest_path=str(manifest),
                out_dir=str(root / "out"),
            )
            counts = payload["metrics"]["primary_bucket_counts"]
            self.assertEqual(counts["single_branch_resolution_without_true_stall"], 1)
            self.assertEqual(counts["noncontributing_branch_sequence"], 1)


if __name__ == "__main__":
    unittest.main()
