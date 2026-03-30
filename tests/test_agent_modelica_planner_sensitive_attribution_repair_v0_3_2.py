from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_planner_sensitive_attribution_repair_v0_3_2 import repair_variant


class AgentModelicaPlannerSensitiveAttributionRepairV032Tests(unittest.TestCase):
    def test_repair_variant_rebuilds_resolution_distribution_from_results(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_planner_sensitive_repair_") as td:
            root = Path(td)
            source = root / "source"
            out = root / "out"
            source.mkdir(parents=True, exist_ok=True)
            (source / "results_baseline.json").write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "t1",
                                "passed": True,
                                "hard_checks": {
                                    "check_model_pass": True,
                                    "simulate_pass": True,
                                    "physics_contract_pass": True,
                                    "regression_pass": True,
                                },
                                "llm_request_count_delta": 1,
                                "llm_plan_used": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (source / "summary_baseline.json").write_text(
                json.dumps({"resolution_path_distribution": {"unresolved": 1}}),
                encoding="utf-8",
            )
            summary = repair_variant(variant="baseline", source_dir=str(source), out_dir=str(out))
            self.assertEqual(summary["success_count"], 1)
            self.assertEqual(summary["resolution_path_distribution"]["llm_planner_assisted"], 1)
            self.assertTrue(any("replaced" in note for note in summary["notes"]))
            self.assertTrue((out / "experience_baseline.json").exists())
            self.assertTrue((out / "summary_baseline.json").exists())


if __name__ == "__main__":
    unittest.main()
