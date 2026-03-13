import unittest
from unittest import mock

from gateforge.agent_modelica_underconstrained_fast_check_v1 import build_underconstrained_fast_check_v1
from gateforge.agent_modelica_underconstrained_fast_check_v1 import _check_model_once


class AgentModelicaUnderconstrainedFastCheckV1Tests(unittest.TestCase):
    def test_check_model_once_uses_mkdtemp_and_ignores_cleanup_errors(self) -> None:
        with mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1._read_text",
            return_value="model A1 end A1;",
        ), mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1._find_primary_model_name",
            return_value="A1",
        ), mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1.tempfile.mkdtemp",
            return_value="/tmp/underconstrained-fast-check",
        ) as mkdtemp_mock, mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1.shutil.copyfile",
            return_value=None,
        ), mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1._run_omc_script_docker",
            return_value=(0, "Check of A1 completed successfully."),
        ), mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1.shutil.rmtree",
            return_value=None,
        ) as rmtree_mock:
            result = _check_model_once(
                model_path="/tmp/source.mo",
                backend="openmodelica_docker",
                docker_image="openmodelica/openmodelica:v1.26.1-minimal",
                timeout_sec=30,
            )

        mkdtemp_mock.assert_called_once()
        rmtree_mock.assert_called_once_with(mock.ANY, ignore_errors=True)
        self.assertTrue(bool(result.get("check_model_pass")))

    def test_check_model_once_cleans_up_workspace_after_runner_failure(self) -> None:
        with mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1._read_text",
            return_value="model A1 end A1;",
        ), mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1._find_primary_model_name",
            return_value="A1",
        ), mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1.tempfile.mkdtemp",
            return_value="/tmp/underconstrained-fast-check",
        ), mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1.shutil.copyfile",
            return_value=None,
        ), mock.patch(
            "gateforge.agent_modelica_underconstrained_fast_check_v1._run_omc_script_docker",
            side_effect=RuntimeError("runner boom"),
        ):
            with mock.patch(
                "gateforge.agent_modelica_underconstrained_fast_check_v1.shutil.rmtree",
                return_value=None,
            ) as rmtree_mock:
                with self.assertRaisesRegex(RuntimeError, "runner boom"):
                    _check_model_once(
                        model_path="/tmp/source.mo",
                        backend="openmodelica_docker",
                        docker_image="openmodelica/openmodelica:v1.26.1-minimal",
                        timeout_sec=30,
                    )
        rmtree_mock.assert_called_once_with(mock.ANY, ignore_errors=True)

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
