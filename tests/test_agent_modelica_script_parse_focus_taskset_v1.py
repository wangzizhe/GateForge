import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaScriptParseFocusTasksetV1Tests(unittest.TestCase):
    def test_empty_mutated_model_path_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            out_taskset = root / "focus_taskset.json"
            out = root / "summary.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "failure_type": "model_check_error", "mutated_model_path": ""},
                            {"task_id": "t2", "failure_type": "model_check_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_script_parse_focus_taskset_v1",
                    "--taskset-in",
                    str(taskset),
                    "--min-tasks",
                    "1",
                    "--max-tasks",
                    "3",
                    "--out-taskset",
                    str(out_taskset),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(summary.get("status"), {"PASS", "NEEDS_REVIEW"})

    def test_selects_tasks_from_first_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            first_attr = root / "first_attr.json"
            out_taskset = root / "focus_taskset.json"
            out = root / "summary.json"

            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "failure_type": "model_check_error", "mutated_model_path": str(root / "m1.mo")},
                            {"task_id": "t2", "failure_type": "model_check_error", "mutated_model_path": str(root / "m2.mo")},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            first_attr.write_text(
                json.dumps(
                    {
                        "rows": [
                            {"task_id": "t2", "first_observed_failure_type": "script_parse_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_script_parse_focus_taskset_v1",
                    "--taskset-in",
                    str(taskset),
                    "--first-failure-attribution",
                    str(first_attr),
                    "--min-tasks",
                    "1",
                    "--max-tasks",
                    "3",
                    "--out-taskset",
                    str(out_taskset),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            focused = json.loads(out_taskset.read_text(encoding="utf-8"))
            tasks = focused.get("tasks") if isinstance(focused.get("tasks"), list) else []
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].get("task_id"), "t2")

    def test_fallback_selects_tasks_with_injected_token(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            run_results = root / "run_results.json"
            out_taskset = root / "focus_taskset.json"
            out = root / "summary.json"
            mutant = root / "mutant.mo"
            mutant.write_text("model A\n  Real x = __gf_state_1;\nend A;\n", encoding="utf-8")
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1", "failure_type": "model_check_error", "mutated_model_path": str(mutant)},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            run_results.write_text(json.dumps({"records": []}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_script_parse_focus_taskset_v1",
                    "--taskset-in",
                    str(taskset),
                    "--run-results",
                    str(run_results),
                    "--min-tasks",
                    "1",
                    "--max-tasks",
                    "3",
                    "--out-taskset",
                    str(out_taskset),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            focused = json.loads(out_taskset.read_text(encoding="utf-8"))
            tasks = focused.get("tasks") if isinstance(focused.get("tasks"), list) else []
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0].get("task_id"), "t1")
            self.assertEqual(tasks[0].get("_focus_reason"), "contains_injected_state_token")


if __name__ == "__main__":
    unittest.main()
