import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def _benchmark_fixture() -> dict:
    base_ir = {
        "schema_version": "modeling_ir_v0",
        "source_meta": {
            "domain": "electrical_analog",
            "source_library": "modelica_standard_library",
            "package_name": "Modelica.Electrical.Analog",
        },
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
        "structural_balance": {"variable_count": 5, "equation_count": 5},
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


class RunAgentModelicaElectricalRealismFrozenTasksetV1Tests(unittest.TestCase):
    def test_script_builds_independent_realism_pack(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_electrical_realism_frozen_taskset_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            benchmark = root / "benchmark.json"
            out_dir = root / "out"
            benchmark.write_text(json.dumps(_benchmark_fixture()), encoding="utf-8")
            env = {
                **os.environ,
                "GATEFORGE_AGENT_ELECTRICAL_REALISM_TASKS_PATH": str(benchmark),
                "GATEFORGE_AGENT_ELECTRICAL_REALISM_OUT_DIR": str(out_dir),
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=300,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("pack_track"), "realism")
            self.assertEqual(summary.get("acceptance_scope"), "independent_validation")
            self.assertEqual(int(summary.get("total_tasks") or 0), 6)
            self.assertEqual(int((summary.get("counts_by_failure_type") or {}).get("underconstrained_system") or 0), 2)
            self.assertEqual(int((summary.get("counts_by_failure_type") or {}).get("connector_mismatch") or 0), 2)
            self.assertEqual(int((summary.get("counts_by_failure_type") or {}).get("initialization_infeasible") or 0), 2)
            self.assertEqual(int((summary.get("counts_by_category") or {}).get("topology_wiring") or 0), 4)
            self.assertEqual(int((summary.get("counts_by_category") or {}).get("initialization") or 0), 2)
            self.assertEqual(manifest.get("pack_id"), "agent_modelica_realism_pack_v1")
            first_task = (taskset.get("tasks") or [])[0] if isinstance(taskset.get("tasks"), list) and (taskset.get("tasks") or []) else {}
            self.assertIn("modelica_standard_library", first_task.get("library_hints", []))
            self.assertIn("modelica.electrical.analog", first_task.get("library_hints", []))
            builder_provenance = manifest.get("builder_provenance") if isinstance(manifest.get("builder_provenance"), dict) else {}
            self.assertTrue(str(builder_provenance.get("builder_source_path") or "").endswith("agent_modelica_electrical_mutant_taskset_v0.py"))
            self.assertTrue(bool(builder_provenance.get("builder_source_sha")))
            self.assertEqual(summary.get("builder_source_sha"), builder_provenance.get("builder_source_sha"))
            self.assertTrue((out_dir / "sha256.json").exists())


if __name__ == "__main__":
    unittest.main()
