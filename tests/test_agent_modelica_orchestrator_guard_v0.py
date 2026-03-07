import unittest

from gateforge.agent_modelica_orchestrator_guard_v0 import detect_no_progress_v0, prioritize_repair_actions_v0


class AgentModelicaOrchestratorGuardV0Tests(unittest.TestCase):
    def test_prioritize_actions_prefers_check_related_for_check_stage(self) -> None:
        actions = [
            "rerun simulate and inspect solver behavior",
            "resolve connector mismatch and rerun checkModel",
            "stabilize initialization",
        ]
        ordered = prioritize_repair_actions_v0(actions, expected_stage="check")
        self.assertTrue("checkmodel" in ordered[0].lower() or "connector" in ordered[0].lower())

    def test_detect_no_progress_true_on_repeated_identical_failures(self) -> None:
        attempts = [
            {"observed_failure_type": "model_check_error", "reason": "model check failed", "check_model_pass": False, "simulate_pass": False},
            {"observed_failure_type": "model_check_error", "reason": "model check failed", "check_model_pass": False, "simulate_pass": False},
        ]
        self.assertTrue(detect_no_progress_v0(attempts, window=2))

    def test_detect_no_progress_false_on_progress(self) -> None:
        attempts = [
            {"observed_failure_type": "model_check_error", "reason": "model check failed", "check_model_pass": False, "simulate_pass": False},
            {"observed_failure_type": "simulate_error", "reason": "simulation failed", "check_model_pass": True, "simulate_pass": False},
        ]
        self.assertFalse(detect_no_progress_v0(attempts, window=2))


if __name__ == "__main__":
    unittest.main()
