import unittest

from gateforge.agent_modelica_diagnostic_quality_v0 import evaluate_diagnostic_quality_v0


class AgentModelicaDiagnosticQualityV0Tests(unittest.TestCase):
    def test_quality_metrics_compute_parse_canonical_type_stage(self) -> None:
        run_results = {
            "records": [
                {
                    "task_id": "t1",
                    "attempts": [
                        {
                            "observed_failure_type": "model_check_error",
                            "diagnostic_ir": {"error_type": "model_check_error", "error_subtype": "undefined_symbol", "stage": "check"},
                        },
                        {
                            "observed_failure_type": "simulate_error",
                            "diagnostic_ir": {"error_type": "simulate_error", "error_subtype": "init_failure", "stage": "simulate"},
                        },
                    ],
                }
            ]
        }
        taskset = {"tasks": [{"task_id": "t1", "expected_stage": "simulate"}]}
        summary = evaluate_diagnostic_quality_v0(run_results_payload=run_results, taskset_payload=taskset)
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(float(summary.get("parse_coverage_pct") or 0.0), 100.0)
        self.assertEqual(float(summary.get("canonical_type_match_rate_pct") or 0.0), 100.0)
        self.assertEqual(float(summary.get("type_match_rate_pct") or 0.0), 100.0)
        # stage match is derived from observed failure type first, then fallback expected stage.
        self.assertEqual(float(summary.get("stage_match_rate_pct") or 0.0), 100.0)

    def test_quality_metrics_maps_legacy_script_parse_to_canonical_type(self) -> None:
        run_results = {
            "records": [
                {
                    "task_id": "t2",
                    "attempts": [
                        {
                            "observed_failure_type": "script_parse_error",
                            "diagnostic_ir": {"error_type": "model_check_error", "error_subtype": "parse_lexer_error", "stage": "check"},
                        }
                    ],
                }
            ]
        }
        summary = evaluate_diagnostic_quality_v0(run_results_payload=run_results, taskset_payload={"tasks": []})
        self.assertEqual(float(summary.get("canonical_type_match_rate_pct") or 0.0), 100.0)
        subtype_distribution = summary.get("subtype_distribution") if isinstance(summary.get("subtype_distribution"), dict) else {}
        self.assertEqual(int(subtype_distribution.get("parse_lexer_error") or 0), 1)

    def test_quality_metrics_reports_low_confidence_rate(self) -> None:
        run_results = {
            "records": [
                {
                    "task_id": "t3",
                    "attempts": [
                        {
                            "observed_failure_type": "model_check_error",
                            "diagnostic_ir": {
                                "error_type": "model_check_error",
                                "error_subtype": "parse_lexer_error",
                                "stage": "check",
                                "confidence": 0.4,
                            },
                        },
                        {
                            "observed_failure_type": "simulate_error",
                            "diagnostic_ir": {
                                "error_type": "simulate_error",
                                "error_subtype": "init_failure",
                                "stage": "simulate",
                                "confidence": 0.9,
                            },
                        },
                    ],
                }
            ]
        }
        summary = evaluate_diagnostic_quality_v0(
            run_results_payload=run_results,
            taskset_payload={"tasks": []},
            low_confidence_threshold=0.65,
        )
        self.assertEqual(int(summary.get("low_confidence_count") or 0), 1)
        self.assertEqual(float(summary.get("low_confidence_rate_pct") or 0.0), 50.0)

    def test_quality_metrics_treats_no_comparable_type_stage_as_not_applicable(self) -> None:
        run_results = {
            "records": [
                {
                    "task_id": "t4",
                    "attempts": [
                        {
                            "observed_failure_type": "none",
                            "diagnostic_ir": {"error_type": "none", "error_subtype": "none", "stage": "none"},
                        }
                    ],
                }
            ]
        }
        summary = evaluate_diagnostic_quality_v0(run_results_payload=run_results, taskset_payload={"tasks": []})
        self.assertEqual(float(summary.get("canonical_type_match_rate_pct") or 0.0), 100.0)
        self.assertEqual(float(summary.get("stage_match_rate_pct") or 0.0), 100.0)
        self.assertEqual(int(summary.get("type_comparable_count") or 0), 0)
        self.assertEqual(int(summary.get("stage_comparable_count") or 0), 0)
        self.assertTrue(bool(summary.get("type_match_not_applicable")))
        self.assertTrue(bool(summary.get("stage_match_not_applicable")))


if __name__ == "__main__":
    unittest.main()
