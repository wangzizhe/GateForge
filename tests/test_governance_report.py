import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernanceReportTests(unittest.TestCase):
    def test_governance_report_flags_strategy_switch_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repair = {
                "strategy_compare": {
                    "from_profile": "default",
                    "to_profile": "industrial_strict",
                    "relation": "upgraded",
                    "recommended_profile": "industrial_strict",
                }
            }
            review = {
                "kpis": {
                    "review_recovery_rate": 0.9,
                    "strict_non_pass_rate": 0.1,
                    "approval_rate": 0.8,
                    "fail_rate": 0.1,
                }
            }
            matrix = {"matrix_status": "PASS"}

            rp = root / "repair.json"
            lp = root / "ledger.json"
            mp = root / "matrix.json"
            out = root / "summary.json"
            rp.write_text(json.dumps(repair), encoding="utf-8")
            lp.write_text(json.dumps(review), encoding="utf-8")
            mp.write_text(json.dumps(matrix), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_report",
                    "--repair-batch-summary",
                    str(rp),
                    "--review-ledger-summary",
                    str(lp),
                    "--ci-matrix-summary",
                    str(mp),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("strategy_profile_switch_recommended", payload.get("risks", []))
            self.assertEqual(payload.get("kpis", {}).get("recommended_profile"), "industrial_strict")

    def test_governance_report_accepts_orchestrate_strategy_compare_schema(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repair = {
                "strategy_compare": {
                    "from_profile": "default",
                    "to_profile": "industrial_strict",
                    "relation": "downgraded",
                }
            }
            review = {
                "kpis": {
                    "review_recovery_rate": 0.9,
                    "strict_non_pass_rate": 0.1,
                    "approval_rate": 0.8,
                    "fail_rate": 0.1,
                }
            }
            matrix = {"matrix_status": "PASS"}

            rp = root / "repair.json"
            lp = root / "ledger.json"
            mp = root / "matrix.json"
            out = root / "summary.json"
            rp.write_text(json.dumps(repair), encoding="utf-8")
            lp.write_text(json.dumps(review), encoding="utf-8")
            mp.write_text(json.dumps(matrix), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_report",
                    "--repair-batch-summary",
                    str(rp),
                    "--review-ledger-summary",
                    str(lp),
                    "--ci-matrix-summary",
                    str(mp),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("strict_profile_downgrade_detected", payload.get("risks", []))
            self.assertEqual(payload.get("kpis", {}).get("strategy_compare_relation"), "downgraded")

    def test_governance_report_needs_review_on_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repair = {
                "pack_id": "p1",
                "profile_compare": {
                    "from_policy_profile": "default",
                    "to_policy_profile": "industrial_strict_v0",
                    "downgrade_count": 1,
                    "strict_downgrade_rate": 0.5,
                },
            }
            review = {
                "kpis": {
                    "review_recovery_rate": 0.8,
                    "strict_non_pass_rate": 0.3,
                    "approval_rate": 0.7,
                    "fail_rate": 0.2,
                },
                "policy_profile_counts": {"default": 2, "industrial_strict_v0": 1},
            }
            matrix = {"matrix_status": "PASS"}

            rp = root / "repair.json"
            lp = root / "ledger.json"
            mp = root / "matrix.json"
            out = root / "summary.json"
            rp.write_text(json.dumps(repair), encoding="utf-8")
            lp.write_text(json.dumps(review), encoding="utf-8")
            mp.write_text(json.dumps(matrix), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_report",
                    "--repair-batch-summary",
                    str(rp),
                    "--review-ledger-summary",
                    str(lp),
                    "--ci-matrix-summary",
                    str(mp),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("strict_profile_downgrade_detected", payload.get("risks", []))

    def test_governance_report_fail_on_matrix_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rp = root / "repair.json"
            lp = root / "ledger.json"
            mp = root / "matrix.json"
            out = root / "summary.json"
            rp.write_text(json.dumps({"profile_compare": {"downgrade_count": 0}}), encoding="utf-8")
            lp.write_text(json.dumps({"kpis": {"review_recovery_rate": 0.9, "strict_non_pass_rate": 0.0}}), encoding="utf-8")
            mp.write_text(json.dumps({"matrix_status": "FAIL"}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_report",
                    "--repair-batch-summary",
                    str(rp),
                    "--review-ledger-summary",
                    str(lp),
                    "--ci-matrix-summary",
                    str(mp),
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
            self.assertIn("ci_matrix_failed", payload.get("risks", []))

    def test_governance_report_with_previous_snapshot_emits_trend(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rp = root / "repair.json"
            lp = root / "ledger.json"
            mp = root / "matrix.json"
            prev = root / "prev.json"
            out = root / "summary.json"
            rp.write_text(
                json.dumps(
                    {
                        "profile_compare": {
                            "downgrade_count": 1,
                            "strict_downgrade_rate": 0.4,
                        }
                    }
                ),
                encoding="utf-8",
            )
            lp.write_text(
                json.dumps(
                    {
                        "kpis": {
                            "review_recovery_rate": 0.45,
                            "strict_non_pass_rate": 0.6,
                            "approval_rate": 0.4,
                            "fail_rate": 0.6,
                        }
                    }
                ),
                encoding="utf-8",
            )
            mp.write_text(json.dumps({"matrix_status": "PASS"}), encoding="utf-8")
            prev.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "kpis": {
                            "strict_downgrade_rate": 0.0,
                            "review_recovery_rate": 0.8,
                            "strict_non_pass_rate": 0.1,
                            "approval_rate": 0.7,
                            "fail_rate": 0.2,
                        },
                        "risks": ["review_recovery_rate_low"],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_report",
                    "--repair-batch-summary",
                    str(rp),
                    "--review-ledger-summary",
                    str(lp),
                    "--ci-matrix-summary",
                    str(mp),
                    "--previous-summary",
                    str(prev),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            trend = payload.get("trend", {})
            self.assertTrue(trend)
            self.assertEqual(trend.get("status_transition"), "PASS->NEEDS_REVIEW")
            self.assertIn("strict_profile_downgrade_detected", trend.get("new_risks", []))
            self.assertIn("kpi_delta", trend)
            self.assertIn("strategy_compare_relation_transition", trend.get("kpi_delta", {}))
            self.assertIn("recommended_profile_transition", trend.get("kpi_delta", {}))


if __name__ == "__main__":
    unittest.main()
