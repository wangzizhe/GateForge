import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaHardpackTasksetBuilderV1Tests(unittest.TestCase):
    def test_builds_taskset_from_hardpack_cases(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            hardpack = root / "hardpack.json"
            taskset = root / "taskset.json"
            out = root / "summary.json"
            hardpack.write_text(
                json.dumps(
                    {
                        "hardpack_version": "agent_modelica_hardpack_v1",
                        "cases": [
                            {
                                "mutation_id": "m1",
                                "target_scale": "small",
                                "expected_failure_type": "simulate_error",
                                "expected_stage": "simulate",
                                "source_model_path": "a.mo",
                                "mutated_model_path": "a_mut.mo",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_hardpack_taskset_builder_v1",
                    "--hardpack",
                    str(hardpack),
                    "--taskset-out",
                    str(taskset),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("task_count", 0)), 1)
            payload = json.loads(taskset.read_text(encoding="utf-8"))
            tasks = payload.get("tasks", [])
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].get("task_id"), "task_m1")


if __name__ == "__main__":
    unittest.main()
