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

    def test_store_persists_learning_fields_for_training(self) -> None:
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
                                "task_id": "t_learn",
                                "scale": "medium",
                                "failure_type": "simulate_error",
                                "passed": False,
                                "rounds_used": 3,
                                "elapsed_sec": 95.5,
                                "hard_checks": {
                                    "check_model_pass": True,
                                    "simulate_pass": False,
                                    "physics_contract_pass": True,
                                    "regression_pass": True,
                                },
                                "repair_audit": {
                                    "strategy_id": "sim_init_stability",
                                    "actions_planned": [
                                        "stabilize start values",
                                        "bound unstable parameters",
                                        "reduce event chattering",
                                    ],
                                },
                                "regression_reasons": ["runtime_regression:3.0>2.4"],
                            }
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
                                "task_id": "t_learn",
                                "expected_stage": "simulate",
                                "source_model_path": "assets_private/modelica/MediumPlant.mo",
                                "simulate_error_message": "Integrator failed near t=0",
                            }
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
                    "--include-failed",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(memory.read_text(encoding="utf-8"))
            row = (payload.get("rows") or [])[0]
            self.assertEqual(row.get("expected_stage"), "simulate")
            self.assertEqual(row.get("gate_break_reason"), "simulate_fail")
            self.assertTrue(str(row.get("error_signature") or "").startswith("simulate_error:"))
            self.assertTrue("Integrator failed" in str(row.get("error_excerpt") or ""))
            self.assertEqual(row.get("used_strategy"), "sim_init_stability")
            self.assertEqual(row.get("repair_rounds"), 3)
            self.assertEqual(float(row.get("elapsed_sec") or 0.0), 95.5)
            self.assertTrue(str(row.get("patch_diff_summary") or "").startswith("stabilize start values"))


if __name__ == "__main__":
    unittest.main()
