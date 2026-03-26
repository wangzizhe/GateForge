import unittest

from gateforge.agent_modelica_experience_writer_v1 import (
    build_action_contribution_rows,
    build_experience_record,
    classify_action_contribution,
)


class AgentModelicaExperienceWriterV1Tests(unittest.TestCase):
    def test_classify_action_contribution_advancing_to_pass(self) -> None:
        self.assertEqual(
            classify_action_contribution(failure_bucket_before="model_check_error", failure_bucket_after="passed"),
            "advancing",
        )

    def test_classify_action_contribution_regressing_when_stage_drops(self) -> None:
        self.assertEqual(
            classify_action_contribution(failure_bucket_before="simulate_error", failure_bucket_after="model_check_error"),
            "regressing",
        )

    def test_build_action_contribution_rows_uses_next_attempt_bucket(self) -> None:
        run_result = {
            "task_id": "demo",
            "failure_type": "script_parse_error",
            "executor_status": "PASS",
            "check_model_pass": True,
            "simulate_pass": True,
            "physics_contract_pass": True,
            "regression_pass": True,
            "attempts": [
                {
                    "round": 1,
                    "observed_failure_type": "script_parse_error",
                    "pre_repair": {
                        "applied": True,
                        "rule_id": "rule_parse_error_pre_repair",
                        "action_key": "repair|parse_error_pre_repair|rule_engine_v1",
                        "rule_tier": "domain_general_rule",
                        "replay_eligible": True,
                        "failure_bucket_before": "script_parse_error",
                        "failure_bucket_after": "retry_pending",
                    },
                },
                {
                    "round": 2,
                    "observed_failure_type": "none",
                    "check_model_pass": True,
                    "simulate_pass": True,
                },
            ],
        }
        rows = build_action_contribution_rows(run_result)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["rule_id"], "rule_parse_error_pre_repair")
        self.assertEqual(row["failure_bucket_before"], "script_parse_error")
        self.assertEqual(row["failure_bucket_after"], "none")
        self.assertEqual(row["contribution"], "advancing")

    def test_build_experience_record_includes_quality_and_rows(self) -> None:
        run_result = {
            "task_id": "demo",
            "failure_type": "simulate_error",
            "executor_status": "PASS",
            "check_model_pass": True,
            "simulate_pass": True,
            "physics_contract_pass": True,
            "regression_pass": True,
            "live_request_count": 0,
            "attempts": [
                {
                    "round": 1,
                    "observed_failure_type": "simulate_error",
                    "simulate_error_injection_repair": {
                        "applied": True,
                        "rule_id": "rule_simulate_error_injection_repair",
                        "action_key": "repair|simulate_error_injection_repair|rule_engine_v1",
                        "rule_tier": "mutation_contract_rule",
                        "replay_eligible": False,
                        "failure_bucket_before": "simulate_error",
                        "failure_bucket_after": "retry_pending",
                    },
                }
            ],
        }
        record = build_experience_record(run_result)
        self.assertIn("repair_quality_score", record)
        self.assertEqual(len(record["action_contributions"]), 1)


if __name__ == "__main__":
    unittest.main()
