import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RepairBatchTests(unittest.TestCase):
    def _write_source(self, path: Path, *, status: str, decision: str, proposal_id: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": proposal_id,
                    "status": status,
                    "policy_decision": decision,
                    "policy_reasons": ["runtime_regression:1.2s>1.0s"] if decision != "PASS" else [],
                    "fail_reasons": ["regression_fail"] if decision != "PASS" else [],
                }
            ),
            encoding="utf-8",
        )

    def _write_baseline(self, path: Path, backend: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "baseline-1",
                    "backend": backend,
                    "model_script": "examples/openmodelica/minimal_probe.mos",
                    "status": "success",
                    "gate": "PASS",
                    "check_ok": True,
                    "simulate_ok": True,
                    "metrics": {"runtime_seconds": 0.1},
                }
            ),
            encoding="utf-8",
        )

    def test_repair_batch_pass_when_all_cases_recover(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src1 = root / "source1.json"
            src2 = root / "source2.json"
            baseline = root / "baseline_mock.json"
            self._write_source(src1, status="FAIL", decision="FAIL", proposal_id="p1")
            self._write_source(src2, status="FAIL", decision="FAIL", proposal_id="p2")
            self._write_baseline(baseline, backend="mock")

            pack = {
                "pack_id": "repair_batch_unit_pass",
                "cases": [
                    {"name": "case1", "source": str(src1), "baseline": str(baseline), "planner_backend": "rule"},
                    {"name": "case2", "source": str(src2), "baseline": str(baseline), "planner_backend": "rule"},
                ],
            }
            pack_path = root / "pack.json"
            pack_path.write_text(json.dumps(pack), encoding="utf-8")

            out_dir = root / "out"
            summary_out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_batch",
                    "--pack",
                    str(pack_path),
                    "--out-dir",
                    str(out_dir),
                    "--summary-out",
                    str(summary_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(summary_out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_cases"), 2)
            self.assertEqual(payload.get("pass_count"), 2)
            self.assertEqual(payload.get("fail_count"), 0)
            self.assertEqual(payload.get("improved_count"), 2)
            self.assertEqual(payload.get("worse_count"), 0)

    def test_repair_batch_fails_for_mixed_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            recover_src = root / "recover.json"
            worse_src = root / "worse.json"
            baseline_mock = root / "baseline_mock.json"
            baseline_om = root / "baseline_om.json"
            self._write_source(recover_src, status="FAIL", decision="FAIL", proposal_id="p_recover")
            self._write_source(worse_src, status="PASS", decision="PASS", proposal_id="p_worse")
            self._write_baseline(baseline_mock, backend="mock")
            self._write_baseline(baseline_om, backend="openmodelica_docker")

            pack = {
                "pack_id": "repair_batch_unit_mixed",
                "cases": [
                    {
                        "name": "recover_case",
                        "source": str(recover_src),
                        "baseline": str(baseline_mock),
                        "planner_backend": "rule",
                    },
                    {
                        "name": "worse_case",
                        "source": str(worse_src),
                        "baseline": str(baseline_om),
                        "planner_backend": "rule",
                    },
                ],
            }
            pack_path = root / "pack.json"
            pack_path.write_text(json.dumps(pack), encoding="utf-8")

            out_dir = root / "out"
            summary_out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_batch",
                    "--pack",
                    str(pack_path),
                    "--out-dir",
                    str(out_dir),
                    "--summary-out",
                    str(summary_out),
                    "--continue-on-fail",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(summary_out.read_text(encoding="utf-8"))
            statuses = [x.get("status") for x in payload.get("cases", [])]
            self.assertIn("PASS", statuses)
            self.assertIn("FAIL", statuses)
            self.assertGreaterEqual(payload.get("worse_count", 0), 1)

    def test_repair_batch_profile_compare_outputs_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "recover.json"
            baseline = root / "baseline_mock.json"
            self._write_source(src, status="FAIL", decision="FAIL", proposal_id="p_compare")
            self._write_baseline(baseline, backend="mock")

            pack = {
                "pack_id": "repair_batch_unit_compare",
                "cases": [
                    {"name": "compare_case", "source": str(src), "baseline": str(baseline), "planner_backend": "rule"},
                ],
            }
            pack_path = root / "pack.json"
            pack_path.write_text(json.dumps(pack), encoding="utf-8")

            summary_out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.repair_batch",
                    "--pack",
                    str(pack_path),
                    "--summary-out",
                    str(summary_out),
                    "--compare-policy-profiles",
                    "industrial_strict_v0",
                    "industrial_strict_v0",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn(proc.returncode, {0, 1}, msg=proc.stderr or proc.stdout)
            payload = json.loads(summary_out.read_text(encoding="utf-8"))
            compare = payload.get("profile_compare", {})
            self.assertEqual(compare.get("from_policy_profile"), "industrial_strict_v0")
            self.assertEqual(compare.get("to_policy_profile"), "industrial_strict_v0")
            self.assertEqual(compare.get("total_compared_cases"), 1)
            self.assertIn("strict_downgrade_rate", compare)
            self.assertTrue(compare.get("transitions"))
            reason_dist = compare.get("reason_distribution", {})
            self.assertIn("from_counts", reason_dist)
            self.assertIn("to_counts", reason_dist)
            self.assertIn("delta_counts", reason_dist)


if __name__ == "__main__":
    unittest.main()
