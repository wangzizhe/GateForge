import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RepairOrchestrateTests(unittest.TestCase):
    def test_repair_orchestrate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_fail.json"
            out_dir = root / "out"
            out = root / "summary.json"
            source.write_text(
                json.dumps(
                    {
                        "proposal_id": "orchestrate-001",
                        "status": "FAIL",
                        "policy_decision": "FAIL",
                        "risk_level": "low",
                        "policy_reasons": ["runtime_regression:1.2s>1.0s"],
                        "fail_reasons": ["regression_fail"],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_orchestrate",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "rule",
                    "--strategy-profile",
                    "default",
                    "--baseline",
                    "baselines/mock_minimal_probe_baseline.json",
                    "--out-dir",
                    str(out_dir),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertTrue((out_dir / "tasks.json").exists())
            self.assertTrue((out_dir / "pack.json").exists())
            self.assertTrue((out_dir / "batch_summary.json").exists())

    def test_repair_orchestrate_compare_profiles_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_fail.json"
            out_dir = root / "out"
            out = root / "summary_compare.json"
            source.write_text(
                json.dumps(
                    {
                        "proposal_id": "orchestrate-compare-001",
                        "status": "FAIL",
                        "policy_decision": "FAIL",
                        "risk_level": "medium",
                        "policy_reasons": ["runtime_regression:1.4s>1.0s"],
                        "fail_reasons": ["regression_fail"],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_orchestrate",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "rule",
                    "--compare-strategy-profiles",
                    "default",
                    "industrial_strict",
                    "--baseline",
                    "baselines/mock_minimal_probe_baseline.json",
                    "--out-dir",
                    str(out_dir),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            compare = payload.get("compare", {})
            self.assertEqual(compare.get("strategy_profile"), "industrial_strict")
            self.assertIn(compare.get("batch_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            compare_delta = payload.get("strategy_compare", {})
            self.assertEqual(compare_delta.get("from_profile"), "default")
            self.assertEqual(compare_delta.get("to_profile"), "industrial_strict")
            self.assertIn(compare_delta.get("relation"), {"upgraded", "unchanged", "downgraded"})
            self.assertTrue((out_dir / "compare_industrial_strict" / "tasks.json").exists())

    def test_repair_orchestrate_compare_profiles_fail_if_compare_side_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source_fail.json"
            out_dir = root / "out"
            out = root / "summary_compare_fail.json"
            source.write_text(
                json.dumps(
                    {
                        "proposal_id": "orchestrate-compare-fail-001",
                        "status": "FAIL",
                        "policy_decision": "FAIL",
                        "risk_level": "medium",
                        "policy_reasons": ["runtime_regression:1.4s>1.0s"],
                        "fail_reasons": ["regression_fail"],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_orchestrate",
                    "--source",
                    str(source),
                    "--planner-backend",
                    "rule",
                    "--compare-strategy-profiles",
                    "default",
                    "missing_profile",
                    "--baseline",
                    "baselines/mock_minimal_probe_baseline.json",
                    "--out-dir",
                    str(out_dir),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            compare = payload.get("compare", {})
            self.assertEqual(compare.get("strategy_profile"), "missing_profile")
            self.assertEqual(compare.get("status"), "FAIL")
            self.assertIn("repair_pack", compare.get("step_exit_codes", {}))
            self.assertNotEqual(compare.get("step_exit_codes", {}).get("repair_pack"), 0)


if __name__ == "__main__":
    unittest.main()
