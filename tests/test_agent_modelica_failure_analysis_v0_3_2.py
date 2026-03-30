from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_failure_analysis_v0_3_2 import (
    analyze_failure_matrix,
    run_failure_analysis,
)


class AgentModelicaFailureAnalysisV032Tests(unittest.TestCase):
    def test_analyze_failure_matrix_flags_persistent_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_failure_matrix_") as td:
            root = Path(td)
            cfg_a = root / "a.json"
            cfg_b = root / "b.json"
            payload = {
                "results": [
                    {
                        "mutation_id": "case_fail",
                        "target_scale": "small",
                        "expected_failure_type": "coupled_conflict_failure",
                        "success": False,
                        "executor_status": "FAILED",
                        "elapsed_sec": 6.0,
                        "rounds_used": 1,
                        "resolution_path": "unresolved",
                        "dominant_stage_subtype": "stage_3_behavioral_contract_semantic",
                        "planner_invoked": True,
                        "planner_used": True,
                        "planner_decisive": False,
                        "replay_used": False,
                    },
                    {
                        "mutation_id": "case_pass",
                        "target_scale": "small",
                        "expected_failure_type": "solver_sensitive_simulate_failure",
                        "success": True,
                        "executor_status": "PASS",
                        "elapsed_sec": 4.0,
                        "rounds_used": 1,
                        "resolution_path": "deterministic_rule_only",
                        "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                        "planner_invoked": False,
                        "planner_used": False,
                        "planner_decisive": False,
                        "replay_used": False,
                    },
                ]
            }
            cfg_a.write_text(json.dumps(payload), encoding="utf-8")
            cfg_b.write_text(json.dumps(payload), encoding="utf-8")
            result = analyze_failure_matrix(
                [
                    {"config_label": "baseline", "results_path": str(cfg_a)},
                    {"config_label": "planner_only", "results_path": str(cfg_b)},
                ]
            )
            self.assertEqual(result["persistent_failure_count"], 1)
            self.assertEqual(result["persistent_failures"][0]["mutation_id"], "case_fail")
            self.assertTrue(result["persistent_failures"][0]["planner_invoked_any"])

    def test_run_failure_analysis_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_failure_analysis_") as td:
            root = Path(td)
            cfg = root / "cfg.json"
            cfg.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "case_fail",
                                "target_scale": "small",
                                "expected_failure_type": "coupled_conflict_failure",
                                "success": False,
                                "executor_status": "FAILED",
                                "elapsed_sec": 6.0,
                                "rounds_used": 1,
                                "resolution_path": "unresolved",
                                "dominant_stage_subtype": "stage_3_behavioral_contract_semantic",
                                "planner_invoked": True,
                                "planner_used": True,
                                "planner_decisive": False,
                                "replay_used": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = run_failure_analysis(
                out_dir=str(root / "out"),
                configs=[{"config_label": "baseline", "results_path": str(cfg)}],
            )
            self.assertEqual(payload["persistent_failure_count"], 1)
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "summary.md").exists())


if __name__ == "__main__":
    unittest.main()
