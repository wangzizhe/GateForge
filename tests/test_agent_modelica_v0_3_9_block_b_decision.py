from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_9_block_b_decision import build_v0_3_9_block_b_decision


class AgentModelicaV039BlockBDecisionTests(unittest.TestCase):
    def test_supports_replacement_hypothesis_when_one_bucket_covers_80_percent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mainline = root / "mainline.json"
            mainline.write_text(json.dumps({"task_count": 10}), encoding="utf-8")
            contrast = root / "contrast.json"
            contrast.write_text(json.dumps({"task_count": 5}), encoding="utf-8")
            classifier = root / "classifier.json"
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 5,
                            "primary_bucket_counts": {
                                "single_branch_resolution_without_true_stall": 4,
                                "noncontributing_branch_sequence": 1,
                                "explicit_switch_subfamily_misalignment": 0,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_9_block_b_decision(
                mainline_manifest_path=str(mainline),
                contrast_manifest_path=str(contrast),
                absorbed_classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["decision"], "replacement_hypothesis_supported")
            self.assertEqual(payload["replacement_hypothesis"], "single_branch_resolution_without_true_stall")


if __name__ == "__main__":
    unittest.main()
