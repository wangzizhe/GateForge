import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaTasksetLockV1Tests(unittest.TestCase):
    def test_lock_taskset_by_scale_and_failure_type(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            taskset = root / "taskset.json"
            summary = root / "summary.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "target_scale": "small",
                                "expected_failure_type": "model_check_error",
                                "source_model_path": "a.mo",
                                "mutated_model_path": "a1.mo",
                            },
                            {
                                "mutation_id": "m2",
                                "target_scale": "medium",
                                "expected_failure_type": "simulate_error",
                                "source_model_path": "b.mo",
                                "mutated_model_path": "b1.mo",
                            },
                            {
                                "mutation_id": "m3",
                                "target_scale": "large",
                                "expected_failure_type": "semantic_regression",
                                "source_model_path": "c.mo",
                                "mutated_model_path": "c1.mo",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_taskset_lock_v1",
                    "--mutation-manifest",
                    str(manifest),
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
            s = json.loads(summary.read_text(encoding="utf-8"))
            t = json.loads(taskset.read_text(encoding="utf-8"))
            self.assertEqual(s.get("status"), "PASS")
            self.assertEqual(int(s.get("total_tasks", 0)), 3)
            self.assertEqual(len(t.get("tasks", [])), 3)
            first = t.get("tasks", [])[0]
            self.assertIn("baseline_metrics", first)
            self.assertIn("candidate_metrics", first)

    def test_lock_taskset_respects_per_scale_failure_cap(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            taskset = root / "taskset.json"
            summary = root / "summary.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "target_scale": "small",
                                "expected_failure_type": "model_check_error",
                            },
                            {
                                "mutation_id": "m2",
                                "target_scale": "small",
                                "expected_failure_type": "model_check_error",
                            },
                            {
                                "mutation_id": "m3",
                                "target_scale": "small",
                                "expected_failure_type": "simulate_error",
                            },
                            {
                                "mutation_id": "m4",
                                "target_scale": "small",
                                "expected_failure_type": "simulate_error",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_taskset_lock_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--scales",
                    "small",
                    "--failure-types",
                    "model_check_error,simulate_error",
                    "--max-per-scale",
                    "10",
                    "--max-per-scale-failure-type",
                    "1",
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
            s = json.loads(summary.read_text(encoding="utf-8"))
            counts = (s.get("counts_by_scale_failure_type") or {}).get("small") or {}
            self.assertEqual(int(counts.get("model_check_error", 0)), 1)
            self.assertEqual(int(counts.get("simulate_error", 0)), 1)
            self.assertEqual(int(s.get("total_tasks", 0)), 2)


if __name__ == "__main__":
    unittest.main()
