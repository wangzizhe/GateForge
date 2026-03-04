import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaTasksetReplayInjectorV1Tests(unittest.TestCase):
    def test_injects_hard_fail_then_slow_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current_taskset = root / "current.json"
            prev_taskset = root / "prev_taskset.json"
            prev_results = root / "prev_results.json"
            out_taskset = root / "out_taskset.json"
            out_summary = root / "summary.json"

            current_taskset.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_taskset_v1",
                        "snapshot_version": "w10",
                        "tasks": [
                            {"task_id": "task_a", "failure_type": "simulate_error"},
                            {"task_id": "task_b", "failure_type": "model_check_error"},
                            {"task_id": "task_c", "failure_type": "semantic_regression"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            prev_taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "task_x", "failure_type": "simulate_error"},
                            {"task_id": "task_y", "failure_type": "model_check_error"},
                            {"task_id": "task_z", "failure_type": "semantic_regression"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            prev_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "task_x",
                                "passed": False,
                                "elapsed_sec": 10,
                                "hard_checks": {"simulate_pass": False},
                            },
                            {
                                "task_id": "task_y",
                                "passed": True,
                                "elapsed_sec": 40,
                                "hard_checks": {
                                    "check_model_pass": True,
                                    "simulate_pass": True,
                                    "physics_contract_pass": True,
                                    "regression_pass": True,
                                },
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
                    "gateforge.agent_modelica_taskset_replay_injector_v1",
                    "--current-taskset",
                    str(current_taskset),
                    "--prev-taskset",
                    str(prev_taskset),
                    "--prev-run-results",
                    str(prev_results),
                    "--max-replay",
                    "2",
                    "--out-taskset",
                    str(out_taskset),
                    "--out",
                    str(out_summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out_summary.read_text(encoding="utf-8"))
            self.assertEqual(int(summary.get("injected_replay_count", 0)), 2)
            mixed = summary.get("injected_mix", {})
            self.assertEqual(int(mixed.get("hard_fail", 0)), 1)
            self.assertEqual(int(mixed.get("slow_pass", 0)), 1)

            out = json.loads(out_taskset.read_text(encoding="utf-8"))
            tasks = out.get("tasks", [])
            self.assertEqual(len(tasks), 3)
            self.assertEqual(tasks[0].get("task_id"), "task_x")
            self.assertEqual(tasks[0].get("_replay_class"), "hard_fail")
            self.assertEqual(tasks[1].get("task_id"), "task_y")
            self.assertEqual(tasks[1].get("_replay_class"), "slow_pass")


if __name__ == "__main__":
    unittest.main()
