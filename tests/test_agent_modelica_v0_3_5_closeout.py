from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_5_closeout import build_v0_3_5_closeout


class AgentModelicaV035CloseoutTests(unittest.TestCase):
    def test_build_v0_3_5_closeout_classifies_frontier_advanced(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v035_closeout_") as td:
            root = Path(td)
            dev = root / "dev.json"
            promotion = root / "promotion.json"
            classifier = root / "classifier.json"
            previous = root / "previous.json"
            dev.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "primary_repair_lever": {"lever": "simulate_error_parameter_recovery_sweep"},
                        "best_harder_lane": {"family_id": "post_restore_residual_conflict", "status": "FREEZE_READY"},
                    }
                ),
                encoding="utf-8",
            )
            promotion.write_text(
                json.dumps(
                    {
                        "status": "PROMOTION_READY",
                        "decision": {"promote": True},
                        "observed_metrics": {
                            "success_rate_pct": 100.0,
                            "planner_invoked_pct": 100.0,
                            "deterministic_only_pct": 0.0,
                            "rule_then_llm_rate_pct": 100.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "metrics": {
                            "post_restore_progress_rate_pct": 100.0,
                            "failure_bucket_counts": {"success_after_restore": 10},
                        },
                    }
                ),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps(
                    {
                        "classification": "development_frontier_advanced_multi_round_promoted",
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_5_closeout(
                dev_priorities_summary_path=str(dev),
                promotion_summary_path=str(promotion),
                post_restore_classifier_summary_path=str(classifier),
                previous_closeout_summary_path=str(previous),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "PASS")
        self.assertEqual(payload.get("classification"), "post_restore_frontier_advanced_parameter_recovery_promoted")


if __name__ == "__main__":
    unittest.main()
