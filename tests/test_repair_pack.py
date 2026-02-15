import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RepairPackTests(unittest.TestCase):
    def test_generate_pack_from_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            tasks = root / "tasks.json"
            out = root / "pack.json"
            tasks.write_text(
                json.dumps(
                    {
                        "source_path": "artifacts/source_fail.json",
                        "risk_level": "medium",
                        "policy_decision": "FAIL",
                        "task_count": 5,
                        "strategy_counts": {"tune_runtime_or_solver_config": 1},
                        "tasks": [
                            {
                                "id": "T008",
                                "category": "fix_plan",
                                "priority": "P0",
                                "reason": "runtime_regression:1.2s>1.0s",
                                "recommended_strategy": "tune_runtime_or_solver_config",
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
                    "gateforge.repair_pack",
                    "--tasks-summary",
                    str(tasks),
                    "--pack-id",
                    "unit_pack",
                    "--policy-profile",
                    "industrial_strict_v0",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("pack_id"), "unit_pack")
            self.assertEqual(len(payload.get("cases", [])), 1)
            self.assertEqual(payload["cases"][0].get("max_retries"), 2)
            self.assertEqual(payload["cases"][0].get("policy_profile"), "industrial_strict_v0")
            self.assertTrue(str(payload.get("strategy_profile_path", "")).endswith("default.json"))

    def test_generate_pack_fallback_case(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            tasks = root / "tasks_empty.json"
            out = root / "pack_empty.json"
            tasks.write_text(
                json.dumps(
                    {
                        "source_path": "artifacts/source_fail.json",
                        "risk_level": "high",
                        "tasks": [],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_pack",
                    "--tasks-summary",
                    str(tasks),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(payload.get("cases", [])), 1)
            self.assertEqual(payload["cases"][0].get("name"), "01_generic_repair")
            self.assertEqual(payload["cases"][0].get("max_retries"), 0)

    def test_generate_pack_with_industrial_strategy_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            tasks = root / "tasks_industrial.json"
            out = root / "pack_industrial.json"
            tasks.write_text(
                json.dumps(
                    {
                        "source_path": "artifacts/source_fail.json",
                        "risk_level": "low",
                        "tasks": [
                            {
                                "id": "T001",
                                "category": "fix_plan",
                                "priority": "P1",
                                "reason": "runtime_regression:1.2s>1.0s",
                                "recommended_strategy": "tune_runtime_or_solver_config",
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
                    "gateforge.repair_pack",
                    "--tasks-summary",
                    str(tasks),
                    "--strategy-profile",
                    "industrial_strict",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            case = payload["cases"][0]
            self.assertEqual(case.get("policy_profile"), "industrial_strict_v0")
            self.assertAlmostEqual(float(case.get("retry_confidence_min")), 0.92, places=2)
            self.assertTrue(str(payload.get("strategy_profile_path", "")).endswith("industrial_strict.json"))


if __name__ == "__main__":
    unittest.main()
