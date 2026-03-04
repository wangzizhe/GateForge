import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaRepairMemoryStoreV1Tests(unittest.TestCase):
    def test_store_writes_private_memory_and_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_results = root / "run_results.json"
            taskset = root / "taskset.json"
            memory = root / "data" / "private_failure_corpus" / "repair_memory.json"
            out = root / "summary.json"

            run_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "t1",
                                "scale": "large",
                                "failure_type": "model_check_error",
                                "passed": True,
                                "hard_checks": {"regression_pass": True},
                                "repair_strategy": {
                                    "strategy_id": "mc_undefined_symbol_guard",
                                    "actions": ["declare missing symbol and align declaration scope"],
                                },
                            },
                            {
                                "task_id": "t2",
                                "scale": "large",
                                "failure_type": "model_check_error",
                                "passed": True,
                                "hard_checks": {"regression_pass": True},
                                "repair_strategy": {
                                    "strategy_id": "mc_undefined_symbol_guard",
                                    "actions": ["declare missing symbol and align declaration scope"],
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "source_model_path": "assets_private/modelica/LargeGrid.mo",
                            },
                            {
                                "task_id": "t2",
                                "source_model_path": "assets_private/modelica/LargeGrid.mo",
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
                    "gateforge.agent_modelica_repair_memory_store_v1",
                    "--run-results",
                    str(run_results),
                    "--taskset",
                    str(taskset),
                    "--memory",
                    str(memory),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            payload = json.loads(memory.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_rows", 0)), 1)
            self.assertEqual(int(summary.get("added_rows", 0)), 1)
            rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("used_strategy"), "mc_undefined_symbol_guard")
            self.assertTrue(rows[0].get("success"))

    def test_store_blocks_non_private_memory_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_results = root / "run_results.json"
            memory = root / "public" / "repair_memory.json"
            out = root / "summary.json"
            run_results.write_text(json.dumps({"records": []}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_repair_memory_store_v1",
                    "--run-results",
                    str(run_results),
                    "--memory",
                    str(memory),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")
            self.assertIn("non_private_memory_path_blocked", summary.get("reasons", []))
            self.assertFalse(memory.exists())

    def test_store_allow_non_private_override(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_results = root / "run_results.json"
            memory = root / "public" / "repair_memory.json"
            out = root / "summary.json"
            run_results.write_text(json.dumps({"records": []}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_repair_memory_store_v1",
                    "--run-results",
                    str(run_results),
                    "--memory",
                    str(memory),
                    "--allow-non-private",
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
            self.assertTrue(memory.exists())


if __name__ == "__main__":
    unittest.main()
