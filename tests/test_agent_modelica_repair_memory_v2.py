import unittest

from gateforge.agent_modelica_repair_memory_v2 import build_repair_memory_v2_from_records


class AgentModelicaRepairMemoryV2Tests(unittest.TestCase):
    def test_build_repair_memory_v2_from_records_uses_action_contributions(self) -> None:
        payload = build_repair_memory_v2_from_records(
            {
                "records": [
                    {
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
                ]
            }
        )
        trajectory_rows = payload.get("trajectory_rows") if isinstance(payload.get("trajectory_rows"), list) else []
        self.assertEqual(len(trajectory_rows), 1)
        self.assertEqual(trajectory_rows[0].get("contribution"), "advancing")
        action_effectiveness = payload.get("action_effectiveness") if isinstance(payload.get("action_effectiveness"), list) else []
        self.assertEqual(len(action_effectiveness), 1)
        self.assertEqual(action_effectiveness[0].get("advancing_count"), 1)
        self.assertEqual(action_effectiveness[0].get("average_quality_score"), 0.95)


if __name__ == "__main__":
    unittest.main()
