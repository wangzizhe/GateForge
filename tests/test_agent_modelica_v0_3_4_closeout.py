from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_4_closeout import build_v0_3_4_closeout


class AgentModelicaV034CloseoutTests(unittest.TestCase):
    def test_build_v0_3_4_closeout_classifies_frontier_advanced(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v034_closeout_") as td:
            root = Path(td)
            dev = root / "dev.json"
            promotion = root / "promotion.json"
            previous = root / "previous.json"

            dev.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "primary_repair_lever": {"lever": "multi_round_deterministic_repair_validation"},
                        "top_bottleneck_lever": {"lever": "repair_rule_ordering"},
                        "best_harder_lane": {"family_id": "hard_multiround_simulate_failure", "status": "FREEZE_READY"},
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
                            "applicable_multi_round_rows": 5,
                            "deterministic_multi_round_rescue_count": 5,
                            "deterministic_multi_round_rescue_rate_pct": 100.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps(
                    {
                        "classification": "development_priorities_shifted_comparative_path_retained",
                    }
                ),
                encoding="utf-8",
            )

            payload = build_v0_3_4_closeout(
                dev_priorities_summary_path=str(dev),
                promotion_summary_path=str(promotion),
                previous_closeout_summary_path=str(previous),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["classification"], "development_frontier_advanced_multi_round_promoted")
        self.assertEqual(payload["metrics"]["deterministic_multi_round_rescue_count"], 5)


if __name__ == "__main__":
    unittest.main()
