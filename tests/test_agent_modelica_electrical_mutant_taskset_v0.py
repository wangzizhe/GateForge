import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _benchmark_fixture() -> dict:
    base_ir = {
        "schema_version": "modeling_ir_v0",
        "source_meta": {"domain": "electrical_analog"},
        "components": [
            {"id": "V1", "type": "Modelica.Electrical.Analog.Sources.ConstantVoltage", "params": {"V": 10.0}},
            {"id": "R1", "type": "Modelica.Electrical.Analog.Basic.Resistor", "params": {"R": 100.0}},
            {"id": "C1", "type": "Modelica.Electrical.Analog.Basic.Capacitor", "params": {"C": 0.01}},
            {"id": "VS1", "type": "Modelica.Electrical.Analog.Sensors.VoltageSensor", "params": {}},
            {"id": "G", "type": "Modelica.Electrical.Analog.Basic.Ground", "params": {}},
        ],
        "connections": [
            {"from": "V1.p", "to": "R1.p"},
            {"from": "R1.n", "to": "C1.p"},
            {"from": "C1.n", "to": "V1.n"},
            {"from": "V1.n", "to": "G.p"},
            {"from": "VS1.p", "to": "C1.p"},
            {"from": "VS1.n", "to": "G.p"},
        ],
        "simulation": {"start_time": 0.0, "stop_time": 1.0, "number_of_intervals": 200, "tolerance": 1e-6, "method": "dassl"},
        "validation_targets": ["VS1.v"],
    }
    return {
        "schema_version": "agent_modelica_electrical_tasks_v0",
        "component_whitelist": [
            "Modelica.Electrical.Analog.Basic.Resistor",
            "Modelica.Electrical.Analog.Basic.Capacitor",
            "Modelica.Electrical.Analog.Basic.Ground",
            "Modelica.Electrical.Analog.Sources.ConstantVoltage",
            "Modelica.Electrical.Analog.Sensors.VoltageSensor",
        ],
        "tasks": [
            {"task_id": "t_small", "scale": "small", "ir": {**base_ir, "model_name": "SmallModel"}},
            {"task_id": "t_medium", "scale": "medium", "ir": {**base_ir, "model_name": "MediumModel"}},
            {"task_id": "t_large", "scale": "large", "ir": {**base_ir, "model_name": "LargeModel"}},
        ],
    }


class AgentModelicaElectricalMutantTasksetV0Tests(unittest.TestCase):
    def test_builder_creates_taskset_and_mutants(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark = root / "benchmark.json"
            taskset = root / "taskset.json"
            summary = root / "summary.json"
            benchmark.write_text(json.dumps(_benchmark_fixture()), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_electrical_mutant_taskset_v0",
                    "--benchmark",
                    str(benchmark),
                    "--source-models-dir",
                    str(root / "source"),
                    "--mutants-dir",
                    str(root / "mutants"),
                    "--taskset-out",
                    str(taskset),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary_payload = json.loads(summary.read_text(encoding="utf-8"))
            taskset_payload = json.loads(taskset.read_text(encoding="utf-8"))
            self.assertEqual(summary_payload.get("status"), "PASS")
            self.assertEqual(int(summary_payload.get("total_tasks", 0)), 3)
            self.assertEqual(len(taskset_payload.get("tasks") or []), 3)
            failure_types = {str(x.get("failure_type")) for x in (taskset_payload.get("tasks") or [])}
            self.assertEqual(
                failure_types,
                {"model_check_error", "simulate_error", "semantic_regression"},
            )
            for task in taskset_payload.get("tasks") or []:
                self.assertTrue(Path(str(task.get("source_model_path"))).exists())
                self.assertTrue(Path(str(task.get("mutated_model_path"))).exists())

    def test_builder_expand_failure_types_produces_cross_product(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark = root / "benchmark.json"
            taskset = root / "taskset.json"
            summary = root / "summary.json"
            benchmark.write_text(json.dumps(_benchmark_fixture()), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_electrical_mutant_taskset_v0",
                    "--benchmark",
                    str(benchmark),
                    "--expand-failure-types",
                    "--source-models-dir",
                    str(root / "source"),
                    "--mutants-dir",
                    str(root / "mutants"),
                    "--taskset-out",
                    str(taskset),
                    "--out",
                    str(summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            taskset_payload = json.loads(taskset.read_text(encoding="utf-8"))
            tasks = taskset_payload.get("tasks") or []
            self.assertEqual(len(tasks), 9)
            by_origin: dict[str, set[str]] = {}
            for row in tasks:
                origin = str(row.get("origin_task_id") or "")
                by_origin.setdefault(origin, set()).add(str(row.get("failure_type") or ""))
            self.assertEqual(
                by_origin.get("t_small"),
                {"model_check_error", "simulate_error", "semantic_regression"},
            )


if __name__ == "__main__":
    unittest.main()
