from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_b_attribution_proxy_v0_3_2 import build_proxy_results, run_proxy


class AgentModelicaTrackBAttributionProxyV032Tests(unittest.TestCase):
    def test_build_proxy_results_marks_legacy_success_as_deterministic(self) -> None:
        rows = build_proxy_results(
            {
                "results": [
                    {
                        "mutation_id": "m1",
                        "expected_failure_type": "simulate_error",
                        "target_scale": "small",
                        "success": True,
                        "executor_status": "PASS",
                    }
                ]
            }
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["resolution_path"], "deterministic_rule_only")
        self.assertFalse(rows[0]["planner_invoked"])

    def test_run_proxy_writes_summary_and_proxy_results(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_track_b_proxy_") as td:
            root = Path(td)
            source = root / "gf_results.json"
            source.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "model_check_error",
                                "target_scale": "small",
                                "success": True,
                                "executor_status": "PASS",
                                "check_model_pass": True,
                                "simulate_pass": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            summary = run_proxy(source_path=str(source), out_dir=str(root / "out"))
            self.assertEqual(summary["success_count"], 1)
            self.assertEqual(summary["resolution_path_distribution"]["deterministic_rule_only"], 1)
            self.assertTrue((root / "out" / "proxy_results.json").exists())
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
