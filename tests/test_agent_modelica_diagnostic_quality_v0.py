import unittest

from gateforge.agent_modelica_diagnostic_quality_v0 import evaluate_diagnostic_quality_v0


class AgentModelicaDiagnosticQualityV0Tests(unittest.TestCase):
    def test_quality_metrics_compute_parse_type_stage(self) -> None:
        run_results = {
            "records": [
                {
                    "task_id": "t1",
                    "attempts": [
                        {
                            "observed_failure_type": "model_check_error",
                            "diagnostic_ir": {"error_type": "model_check_error", "stage": "check"},
                        },
                        {
                            "observed_failure_type": "simulate_error",
                            "diagnostic_ir": {"error_type": "simulate_error", "stage": "simulate"},
                        },
                    ],
                }
            ]
        }
        taskset = {"tasks": [{"task_id": "t1", "expected_stage": "simulate"}]}
        summary = evaluate_diagnostic_quality_v0(run_results_payload=run_results, taskset_payload=taskset)
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(float(summary.get("parse_coverage_pct") or 0.0), 100.0)
        self.assertEqual(float(summary.get("type_match_rate_pct") or 0.0), 100.0)
        # 1 out of 2 stages match expected simulate
        self.assertEqual(float(summary.get("stage_match_rate_pct") or 0.0), 50.0)


if __name__ == "__main__":
    unittest.main()
