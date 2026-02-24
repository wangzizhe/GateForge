import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePolicyPatchRollbackAdvisorTests(unittest.TestCase):
    def _write_inputs(
        self,
        root: Path,
        latest_status: str,
        fail_rate: float,
        reject_rate: float,
        delta_fail: float,
        delta_reject: float,
        delta_pairwise: float = 0.0,
    ):
        summary = root / "summary.json"
        trend = root / "trend.json"
        summary.write_text(
            json.dumps(
                {
                    "latest_status": latest_status,
                    "total_records": 10,
                    "status_counts": {"PASS": 6, "NEEDS_REVIEW": 2, "FAIL": 2},
                    "applied_count": 6,
                    "reject_count": 2,
                }
            ),
            encoding="utf-8",
        )
        trend.write_text(
            json.dumps(
                {
                    "status": latest_status,
                    "trend": {
                        "current_fail_rate": fail_rate,
                        "current_reject_rate": reject_rate,
                        "delta_fail_rate": delta_fail,
                        "delta_reject_rate": delta_reject,
                        "delta_pairwise_threshold_enable_rate": delta_pairwise,
                    },
                }
            ),
            encoding="utf-8",
        )
        return summary, trend

    def test_recommends_rollback_when_rates_deteriorate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary, trend = self._write_inputs(root, "PASS", 0.5, 0.4, 0.2, 0.1)
            out = root / "advice.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_rollback_advisor",
                    "--summary",
                    str(summary),
                    "--trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("decision"), "ROLLBACK_RECOMMENDED")
            self.assertTrue(advice.get("rollback_recommended"))
            self.assertTrue(advice.get("reasons"))

    def test_keeps_policy_when_metrics_are_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary, trend = self._write_inputs(root, "PASS", 0.1, 0.1, -0.1, 0.0)
            out = root / "advice.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_rollback_advisor",
                    "--summary",
                    str(summary),
                    "--trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("decision"), "KEEP")
            self.assertFalse(advice.get("rollback_recommended"))
            self.assertEqual(advice.get("reasons"), [])

    def test_recommends_rollback_when_latest_status_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary, trend = self._write_inputs(root, "FAIL", 0.1, 0.1, 0.0, 0.0)
            out = root / "advice.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_rollback_advisor",
                    "--summary",
                    str(summary),
                    "--trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("decision"), "ROLLBACK_RECOMMENDED")
            self.assertIn("latest_status_fail", advice.get("reasons", []))

    def test_recommends_rollback_when_pairwise_threshold_enable_rate_spikes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary, trend = self._write_inputs(root, "PASS", 0.1, 0.1, 0.0, 0.0, delta_pairwise=0.5)
            out = root / "advice.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_rollback_advisor",
                    "--summary",
                    str(summary),
                    "--trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("decision"), "ROLLBACK_RECOMMENDED")
            reasons = advice.get("reasons", [])
            self.assertTrue(any(str(r).startswith("pairwise_threshold_enable_rate_delta_high") for r in reasons))


if __name__ == "__main__":
    unittest.main()
