import unittest

from gateforge.agent_modelica_underconstrained_fast_check_v1 import build_underconstrained_fast_check_v1


class AgentModelicaUnderconstrainedFastCheckV1Tests(unittest.TestCase):
    def test_fast_check_passes_when_all_underconstrained_tasks_fail_at_check(self) -> None:
        taskset = {
            "tasks": [
                {
                    "task_id": "t1",
                    "failure_type": "underconstrained_system",
                    "expected_stage": "check",
                    "mutated_model_path": "/tmp/t1.mo",
                },
                {
                    "task_id": "t2",
                    "failure_type": "underconstrained_system",
                    "expected_stage": "check",
                    "mutated_model_path": "/tmp/t2.mo",
                },
            ]
        }

        def _runner(task: dict) -> dict:
            return {
                "check_model_pass": False,
                "rc": 1,
                "diagnostic_ir": {
                    "error_type": "model_check_error",
                    "error_subtype": "underconstrained_system",
                    "stage": "check",
                    "observed_phase": "check",
                },
            }

        summary = build_underconstrained_fast_check_v1(taskset_payload=taskset, runner=_runner)
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(int(summary.get("pass_count") or 0), 2)
        self.assertEqual(float(summary.get("stage_match_rate_pct") or 0.0), 100.0)

    def test_fast_check_fails_when_underconstrained_stage_drifts(self) -> None:
        taskset = {
            "tasks": [
                {
                    "task_id": "t1",
                    "failure_type": "underconstrained_system",
                    "expected_stage": "check",
                    "mutated_model_path": "/tmp/t1.mo",
                }
            ]
        }

        def _runner(task: dict) -> dict:
            return {
                "check_model_pass": False,
                "rc": 1,
                "diagnostic_ir": {
                    "error_type": "model_check_error",
                    "error_subtype": "underconstrained_system",
                    "stage": "simulate",
                    "observed_phase": "simulate",
                },
            }

        summary = build_underconstrained_fast_check_v1(taskset_payload=taskset, runner=_runner)
        self.assertEqual(summary.get("status"), "FAIL")
        self.assertEqual(int(summary.get("pass_count") or 0), 0)
        self.assertEqual(float(summary.get("stage_match_rate_pct") or 0.0), 0.0)
        self.assertIn("task_failed_fast_check:t1", summary.get("reasons") or [])

    def test_fast_check_blocks_when_modelica_package_is_unavailable(self) -> None:
        taskset = {
            "tasks": [
                {
                    "task_id": "t1",
                    "failure_type": "underconstrained_system",
                    "expected_stage": "check",
                    "mutated_model_path": "/tmp/t1.mo",
                }
            ]
        }

        def _runner(task: dict) -> dict:
            return {
                "check_model_pass": False,
                "rc": 1,
                "output": "Error: Failed to load package Modelica (default). Class Modelica.Electrical.Analog.Basic.Resistor not found in scope X.",
                "diagnostic_ir": {
                    "error_type": "model_check_error",
                    "error_subtype": "undefined_symbol",
                    "stage": "check",
                    "observed_phase": "check",
                },
            }

        summary = build_underconstrained_fast_check_v1(taskset_payload=taskset, runner=_runner)
        self.assertEqual(summary.get("status"), "BLOCKED")
        self.assertEqual(int(summary.get("blocked_count") or 0), 1)
        self.assertIn("blocked:modelica_package_unavailable:t1", summary.get("reasons") or [])

    def test_fast_check_passes_structural_count_mismatch_signal(self) -> None:
        taskset = {
            "tasks": [
                {
                    "task_id": "t1",
                    "failure_type": "underconstrained_system",
                    "expected_stage": "check",
                    "mutated_model_path": "/tmp/t1.mo",
                }
            ]
        }

        def _runner(task: dict) -> dict:
            return {
                "check_model_pass": False,
                "rc": 0,
                "output": "Check of A1 completed successfully.\nClass A1 has 32 equation(s) and 33 variable(s).",
                "diagnostic_ir": {
                    "error_type": "model_check_error",
                    "error_subtype": "underconstrained_system",
                    "stage": "check",
                    "observed_phase": "check",
                },
            }

        summary = build_underconstrained_fast_check_v1(taskset_payload=taskset, runner=_runner)
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(int(summary.get("pass_count") or 0), 1)


if __name__ == "__main__":
    unittest.main()
