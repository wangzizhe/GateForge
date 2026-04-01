from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_10_block_b_decision import build_v0_3_10_block_b_decision


class AgentModelicaV0310BlockBDecisionTests(unittest.TestCase):
    def test_supports_narrower_replacement_when_one_bucket_dominates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lane = root / "lane.json"
            lane.write_text(json.dumps({"lane_status": "NEEDS_MORE_GENERATION"}), encoding="utf-8")
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps({"metrics": {"success_after_same_branch_continuation_count": 0, "same_branch_continuity_success_pct": 0.0, "success_with_explicit_branch_switch_evidence_pct": 0.0}}),
                encoding="utf-8",
            )
            classifier = root / "classifier.json"
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 3,
                            "primary_bucket_counts": {
                                "true_same_branch_multi_step_success": 0,
                                "same_branch_one_shot_or_accidental_success": 3,
                                "hidden_branch_change_misclassified_as_continuity": 0,
                                "stalled_unresolved_same_branch_failure": 0,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_10_block_b_decision(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["decision"], "narrower_replacement_hypothesis_supported")
            self.assertEqual(payload["replacement_hypothesis"], "same_branch_one_shot_or_accidental_success")


if __name__ == "__main__":
    unittest.main()
