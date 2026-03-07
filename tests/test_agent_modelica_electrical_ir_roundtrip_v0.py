import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _benchmark_payload() -> dict:
    return {
        "schema_version": "agent_modelica_electrical_tasks_v0",
        "domain": "electrical_analog",
        "component_whitelist": [
            "Modelica.Electrical.Analog.Basic.Resistor",
            "Modelica.Electrical.Analog.Basic.Capacitor",
            "Modelica.Electrical.Analog.Basic.Ground",
            "Modelica.Electrical.Analog.Sources.ConstantVoltage",
            "Modelica.Electrical.Analog.Sensors.VoltageSensor",
        ],
        "tasks": [
            {
                "task_id": "t1",
                "scale": "small",
                "ir": {
                    "schema_version": "modeling_ir_v0",
                    "model_name": "T1",
                    "source_meta": {"domain": "electrical_analog", "task_id": "t1", "scale": "small"},
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
                    "simulation": {
                        "start_time": 0.0,
                        "stop_time": 1.0,
                        "number_of_intervals": 200,
                        "tolerance": 1e-6,
                        "method": "dassl",
                    },
                    "validation_targets": ["VS1.v"],
                },
            }
        ],
    }


class AgentModelicaElectricalIRRoundtripV0Tests(unittest.TestCase):
    def test_roundtrip_runner_passes_on_valid_task(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark = root / "benchmark.json"
            out = root / "summary.json"
            records_out = root / "records.json"
            modelica_dir = root / "modelica"
            benchmark.write_text(json.dumps(_benchmark_payload()), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_electrical_ir_roundtrip_v0",
                    "--benchmark",
                    str(benchmark),
                    "--modelica-dir",
                    str(modelica_dir),
                    "--records-out",
                    str(records_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            records = json.loads(records_out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_tasks", 0)), 1)
            self.assertEqual(int(summary.get("pass_count", 0)), 1)
            self.assertEqual(records.get("status"), "PASS")
            self.assertEqual(len(records.get("records") or []), 1)
            self.assertTrue(bool((records.get("records") or [])[0].get("roundtrip_match")))


if __name__ == "__main__":
    unittest.main()
