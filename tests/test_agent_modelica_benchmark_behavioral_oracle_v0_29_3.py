from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_benchmark_behavioral_oracle_v0_29_3 import (
    build_behavioral_oracle_summary,
    evaluate_benchmark_behavior,
)


class BenchmarkBehavioralOracleV0293Tests(unittest.TestCase):
    def test_time_constant_behavior_passes_when_fraction_matches(self) -> None:
        task = {
            "verification": {
                "simulate": {"stop_time": 0.5, "intervals": 100},
                "behavioral": {
                    "type": "time_constant",
                    "expected_tau": 0.1,
                    "tolerance": 0.08,
                    "observation_variable": "C1.v",
                },
            }
        }
        data = {"time": [0.0, 0.1, 0.5], "C1.v": [0.0, 0.6321205588, 1.0]}
        with patch(
            "gateforge.agent_modelica_benchmark_behavioral_oracle_v0_29_3._run_simulation_csv",
            return_value=(True, data, ""),
        ):
            result = evaluate_benchmark_behavior(task, "model X\nend X;")
        self.assertTrue(result["pass"])
        self.assertEqual(result["reason"], "time_constant_pass")

    def test_time_constant_behavior_fails_when_fraction_misses(self) -> None:
        task = {
            "verification": {
                "simulate": {"stop_time": 0.5, "intervals": 100},
                "behavioral": {
                    "type": "time_constant",
                    "expected_tau": 0.1,
                    "tolerance": 0.08,
                    "observation_variable": "C1.v",
                },
            }
        }
        data = {"time": [0.0, 0.1, 0.5], "C1.v": [0.0, 0.2, 1.0]}
        with patch(
            "gateforge.agent_modelica_benchmark_behavioral_oracle_v0_29_3._run_simulation_csv",
            return_value=(True, data, ""),
        ):
            result = evaluate_benchmark_behavior(task, "model X\nend X;")
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "time_constant_miss")

    def test_time_constant_behavior_handles_missing_observation_variable(self) -> None:
        task = {
            "verification": {
                "simulate": {"stop_time": 0.5, "intervals": 100},
                "behavioral": {
                    "type": "time_constant",
                    "expected_tau": 0.1,
                    "tolerance": 0.08,
                },
            }
        }
        result = evaluate_benchmark_behavior(task, "model X\nend X;")
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"], "missing_observation_variable_in_task_config")

    def test_build_summary_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_behavioral_oracle_summary(out_dir=Path(tmp))
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((Path(tmp) / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
