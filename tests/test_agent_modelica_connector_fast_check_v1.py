import unittest
from unittest import mock

from gateforge.agent_modelica_connector_fast_check_v1 import build_connector_fast_check_v1
from gateforge.agent_modelica_connector_fast_check_v1 import _check_model_text_once


class AgentModelicaConnectorFastCheckV1Tests(unittest.TestCase):
    def test_check_model_text_once_uses_ignore_cleanup_errors_for_tempdir(self) -> None:
        tempdir_cm = mock.MagicMock()
        tempdir_cm.__enter__.return_value = "/tmp/connector-fast-check"
        tempdir_cm.__exit__.return_value = False

        with mock.patch(
            "gateforge.agent_modelica_connector_fast_check_v1._find_primary_model_name",
            return_value="A1",
        ), mock.patch(
            "gateforge.agent_modelica_connector_fast_check_v1.tempfile.TemporaryDirectory",
            return_value=tempdir_cm,
        ) as tempdir_mock, mock.patch(
            "pathlib.Path.write_text",
            return_value=None,
        ), mock.patch(
            "gateforge.agent_modelica_connector_fast_check_v1._run_omc_script_docker",
            return_value=(0, "Check of A1 completed successfully."),
        ):
            result = _check_model_text_once(
                model_text="model A1 end A1;",
                backend="openmodelica_docker",
                docker_image="openmodelica/openmodelica:v1.26.1-minimal",
                timeout_sec=30,
                task={"expected_stage": "check", "failure_type": "connector_mismatch"},
            )

        tempdir_mock.assert_called_once_with(ignore_cleanup_errors=True)
        self.assertTrue(bool(result.get("check_model_pass")))

    def test_fast_check_passes_when_connector_task_is_repaired_by_endpoint_rewrite(self) -> None:
        taskset = {
            "tasks": [
                {
                    "task_id": "t1",
                    "failure_type": "connector_mismatch",
                    "expected_stage": "check",
                    "mutated_model_path": "/tmp/t1.mo",
                    "mutated_objects": [
                        {
                            "kind": "connection_endpoint",
                            "from": "V1.p",
                            "to_before": "R1.p",
                            "to_after": "R1.badPort",
                        }
                    ],
                }
            ]
        }

        def _runner(task: dict, model_text: str) -> dict:
            if "badPort" in model_text:
                return {
                    "check_model_pass": False,
                    "rc": 1,
                    "output": "Error: Variable R1.badPort not found in scope A1.",
                    "diagnostic_ir": {
                        "error_type": "model_check_error",
                        "error_subtype": "connector_mismatch",
                        "stage": "check",
                        "observed_phase": "check",
                    },
                }
            return {
                "check_model_pass": True,
                "rc": 0,
                "output": "Check of A1 completed successfully.",
                "diagnostic_ir": {
                    "error_type": "none",
                    "error_subtype": "none",
                    "stage": "none",
                    "observed_phase": "none",
                },
            }

        original_read = __import__("gateforge.agent_modelica_connector_fast_check_v1", fromlist=["_read_text"])._read_text
        module = __import__("gateforge.agent_modelica_connector_fast_check_v1", fromlist=["_read_text"])
        module._read_text = lambda _path: "\n".join(
            [
                "model A1",
                "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);",
                "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);",
                "  Modelica.Electrical.Analog.Basic.Ground G1;",
                "equation",
                "  connect(V1.p, R1.badPort);",
                "  connect(R1.n, G1.p);",
                "  connect(V1.n, G1.p);",
                "end A1;",
                "",
            ]
        )
        try:
            summary = build_connector_fast_check_v1(taskset_payload=taskset, runner=_runner)
        finally:
            module._read_text = original_read
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(int(summary.get("pass_count") or 0), 1)
        result = (summary.get("task_results") or [])[0]
        self.assertEqual(result.get("planned_action_op"), "rewrite_connection_endpoint")
        self.assertTrue(bool(result.get("patched_check_model_pass")))

    def test_fast_check_fails_when_connector_diagnostic_does_not_align(self) -> None:
        taskset = {
            "tasks": [
                {
                    "task_id": "t1",
                    "failure_type": "connector_mismatch",
                    "expected_stage": "check",
                    "mutated_model_path": "/tmp/t1.mo",
                    "mutated_objects": [
                        {
                            "kind": "connection_endpoint",
                            "from": "V1.p",
                            "to_before": "R1.p",
                            "to_after": "R1.badPort",
                        }
                    ],
                }
            ]
        }

        def _runner(task: dict, model_text: str) -> dict:
            return {
                "check_model_pass": False,
                "rc": 1,
                "output": "Error: Variable R1.badPort not found in scope A1.",
                "diagnostic_ir": {
                    "error_type": "model_check_error",
                    "error_subtype": "undefined_symbol",
                    "stage": "check",
                    "observed_phase": "check",
                },
            }

        original_read = __import__("gateforge.agent_modelica_connector_fast_check_v1", fromlist=["_read_text"])._read_text
        module = __import__("gateforge.agent_modelica_connector_fast_check_v1", fromlist=["_read_text"])
        module._read_text = lambda _path: "\n".join(
            [
                "model A1",
                "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);",
                "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);",
                "  Modelica.Electrical.Analog.Basic.Ground G1;",
                "equation",
                "  connect(V1.p, R1.badPort);",
                "  connect(R1.n, G1.p);",
                "  connect(V1.n, G1.p);",
                "end A1;",
                "",
            ]
        )
        try:
            summary = build_connector_fast_check_v1(taskset_payload=taskset, runner=_runner)
        finally:
            module._read_text = original_read
        self.assertEqual(summary.get("status"), "FAIL")
        self.assertEqual(int(summary.get("diagnosis_pass_count") or 0), 0)
        self.assertIn("task_failed_fast_check:t1", summary.get("reasons") or [])


if __name__ == "__main__":
    unittest.main()
