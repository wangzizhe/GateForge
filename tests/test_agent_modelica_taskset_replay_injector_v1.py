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

    def test_balances_failure_types_within_hard_fail_selection(self) -> None:
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
                        "tasks": [
                            {"task_id": "task_a", "failure_type": "simulate_error"},
                            {"task_id": "task_b", "failure_type": "simulate_error"},
                            {"task_id": "task_c", "failure_type": "semantic_regression"},
                            {"task_id": "task_d", "failure_type": "model_check_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            prev_taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "h1", "failure_type": "simulate_error"},
                            {"task_id": "h2", "failure_type": "simulate_error"},
                            {"task_id": "h3", "failure_type": "semantic_regression"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            prev_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {"task_id": "h1", "passed": False, "elapsed_sec": 100, "hard_checks": {"simulate_pass": False}},
                            {"task_id": "h2", "passed": False, "elapsed_sec": 90, "hard_checks": {"simulate_pass": False}},
                            {"task_id": "h3", "passed": False, "elapsed_sec": 10, "hard_checks": {"simulate_pass": False}},
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
            out = json.loads(out_taskset.read_text(encoding="utf-8"))
            selected = out.get("tasks", [])[:2]
            selected_ftypes = {str(x.get("failure_type") or "") for x in selected}
            self.assertEqual(selected_ftypes, {"simulate_error", "semantic_regression"})
            self.assertTrue(all(str(x.get("_replay_class") or "") == "hard_fail" for x in selected))

    def test_min_per_failure_type_enforced_when_candidates_exist(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current_taskset = root / "current.json"
            prev_taskset = root / "prev_taskset.json"
            prev_results = root / "prev_results.json"
            out_taskset = root / "out_taskset.json"
            out_summary = root / "summary.json"

            current_taskset.write_text(
                json.dumps({"tasks": [{"task_id": f"task_{i}", "failure_type": "simulate_error"} for i in range(1, 7)]}),
                encoding="utf-8",
            )
            prev_taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "s1", "failure_type": "simulate_error"},
                            {"task_id": "s2", "failure_type": "simulate_error"},
                            {"task_id": "m1", "failure_type": "model_check_error"},
                            {"task_id": "r1", "failure_type": "semantic_regression"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            prev_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {"task_id": "s1", "passed": False, "elapsed_sec": 100, "hard_checks": {"simulate_pass": False}},
                            {"task_id": "s2", "passed": False, "elapsed_sec": 90, "hard_checks": {"simulate_pass": False}},
                            {"task_id": "m1", "passed": False, "elapsed_sec": 5, "hard_checks": {"simulate_pass": False}},
                            {"task_id": "r1", "passed": False, "elapsed_sec": 4, "hard_checks": {"simulate_pass": False}},
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
                    "3",
                    "--min-per-failure-type",
                    "1",
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
            out = json.loads(out_taskset.read_text(encoding="utf-8"))
            selected = out.get("tasks", [])[:3]
            selected_ftypes = {str(x.get("failure_type") or "") for x in selected}
            self.assertEqual(selected_ftypes, {"simulate_error", "model_check_error", "semantic_regression"})


if __name__ == "__main__":
    unittest.main()
