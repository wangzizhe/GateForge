import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePolicyAdvisorTests(unittest.TestCase):
    def test_advisor_suggests_strict_for_high_risk(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            out = root / "advisor.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "kpis": {
                            "risk_score": 80,
                            "latest_mismatch_count": 3,
                        },
                        "risks": ["replay_risk_level_high"],
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps(
                    {
                        "trend": {
                            "kpi_delta": {
                                "history_mismatch_total_delta": 2,
                                "risk_score_delta": 10,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_advisor",
                    "--snapshot",
                    str(snapshot),
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
            self.assertEqual(advice.get("suggested_policy_profile"), "industrial_strict")
            self.assertGreaterEqual(float(advice.get("confidence", 0.0)), 0.8)
            self.assertIn("high_replay_risk_score", advice.get("reasons", []))

    def test_advisor_suggests_default_for_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            out = root / "advisor.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "kpis": {
                            "risk_score": 5,
                            "latest_mismatch_count": 0,
                        },
                        "risks": [],
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps(
                    {
                        "trend": {
                            "kpi_delta": {
                                "history_mismatch_total_delta": -1,
                                "risk_score_delta": -5,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_advisor",
                    "--snapshot",
                    str(snapshot),
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
            self.assertEqual(advice.get("suggested_policy_profile"), "default")
            self.assertIn("stable_replay_signals", advice.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
