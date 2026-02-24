import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneGovernanceAdvisorTests(unittest.TestCase):
    def test_advisor_stable_keep(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dashboard = root / "dashboard.json"
            out = root / "advisor.json"
            dashboard.write_text(
                json.dumps(
                    {
                        "latest_effectiveness_decision": "IMPROVED",
                        "trend_status": "PASS",
                        "improvement_rate": 0.8,
                        "regression_rate": 0.0,
                        "trend_alerts_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_governance_advisor",
                    "--dashboard",
                    str(dashboard),
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
            self.assertEqual(advice.get("action"), "KEEP")
            self.assertEqual(advice.get("suggested_policy_profile"), "default")

    def test_advisor_regressed_tighten(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dashboard = root / "dashboard.json"
            out = root / "advisor.json"
            dashboard.write_text(
                json.dumps(
                    {
                        "latest_effectiveness_decision": "REGRESSED",
                        "trend_status": "NEEDS_REVIEW",
                        "improvement_rate": 0.1,
                        "regression_rate": 0.4,
                        "trend_alerts_count": 2,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_governance_advisor",
                    "--dashboard",
                    str(dashboard),
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
            self.assertEqual(advice.get("action"), "TIGHTEN")
            self.assertEqual(advice.get("suggested_policy_profile"), "industrial_strict")
            patch = advice.get("threshold_patch", {})
            self.assertEqual(patch.get("require_min_top_score_margin"), 2)
            self.assertEqual(patch.get("require_min_explanation_quality"), 85)

    def test_advisor_tightens_on_weak_compare_explanation_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dashboard = root / "dashboard.json"
            out = root / "advisor.json"
            dashboard.write_text(
                json.dumps(
                    {
                        "latest_effectiveness_decision": "IMPROVED",
                        "trend_status": "PASS",
                        "improvement_rate": 0.8,
                        "regression_rate": 0.0,
                        "trend_alerts_count": 0,
                        "tuned_top_score_margin": 1,
                        "tuned_explanation_completeness": 80,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_governance_advisor",
                    "--dashboard",
                    str(dashboard),
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
            self.assertEqual(advice.get("action"), "TIGHTEN")
            self.assertIn("compare_top_score_margin_low", advice.get("reasons", []))
            self.assertIn("compare_explanation_completeness_low", advice.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
