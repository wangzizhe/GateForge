import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaL2ContractSnapshotV0Tests(unittest.TestCase):
    def test_snapshot_exports_contract_and_samples(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark = root / "benchmark.json"
            benchmark.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_electrical_tasks_v0",
                        "component_whitelist": ["Modelica.Electrical.Analog.Sources.SineVoltage"],
                        "tasks": [
                            {
                                "task_id": "t1",
                                "scale": "small",
                                "ir": {
                                    "schema_version": "modeling_ir_v0",
                                    "model_name": "A",
                                    "components": [],
                                    "connections": [],
                                    "structural_balance": {"variable_count": 1, "equation_count": 1},
                                    "simulation": {
                                        "start_time": 0.0,
                                        "stop_time": 0.2,
                                        "number_of_intervals": 20,
                                        "tolerance": 1e-6,
                                        "method": "dassl",
                                    },
                                    "validation_targets": [],
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = root / "contract.json"
            sample_out = root / "samples.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_l2_contract_snapshot_v0",
                    "--benchmark",
                    str(benchmark),
                    "--sample-count",
                    "1",
                    "--sample-scales",
                    "small",
                    "--out",
                    str(out),
                    "--sample-out",
                    str(sample_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload.get("sample_task_count", 0)), 1)
            self.assertTrue(sample_out.exists())


if __name__ == "__main__":
    unittest.main()
