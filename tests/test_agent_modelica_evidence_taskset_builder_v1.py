import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaEvidenceTasksetBuilderV1Tests(unittest.TestCase):
    def test_build_evidence_taskset_for_medium_large(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_taskset = root / "evidence_taskset.json"
            out_summary = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "scale": "small", "failure_type": "model_check_error"},
                            {"task_id": "t2", "scale": "medium", "failure_type": "simulate_error"},
                            {"task_id": "t3", "scale": "large", "failure_type": "semantic_regression"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_evidence_taskset_builder_v1",
                    "--taskset",
                    str(taskset),
                    "--include-scales",
                    "medium,large",
                    "--taskset-out",
                    str(out_taskset),
                    "--out",
                    str(out_summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out_taskset.read_text(encoding="utf-8"))
            tasks = payload.get("tasks", [])
            self.assertEqual(len(tasks), 2)
            self.assertEqual(set(x.get("scale") for x in tasks), {"medium", "large"})
            self.assertTrue(all(isinstance(x.get("baseline_evidence"), dict) for x in tasks))
            self.assertTrue(all(isinstance(x.get("candidate_evidence"), dict) for x in tasks))


if __name__ == "__main__":
    unittest.main()
