import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneAdvisorTests(unittest.TestCase):
    def test_advisor_stable_signals_default(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            governance = root / "governance.json"
            mutation = root / "mutation.json"
            medium = root / "medium.json"
            out = root / "advisor.json"
            governance.write_text(
                json.dumps({"status": "PASS", "kpis": {"strict_non_pass_rate": 0.1}, "risks": []}),
                encoding="utf-8",
            )
            mutation.write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "latest_match_rate": 1.0,
                        "latest_gate_pass_rate": 1.0,
                        "compare_decision": "PASS",
                        "trend_status": "PASS",
                    }
                ),
                encoding="utf-8",
            )
            medium.write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "pass_rate": 1.0,
                        "mismatch_case_count": 0,
                        "trend_delta_pass_rate": 0.0,
                        "advisor_decision": "KEEP",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_advisor",
                    "--governance-snapshot",
                    str(governance),
                    "--mutation-dashboard",
                    str(mutation),
                    "--medium-dashboard",
                    str(medium),
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
            self.assertIn("cross_layer_signals_stable", advice.get("reasons", []))

    def test_advisor_regression_signals_tighten(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            governance = root / "governance.json"
            mutation = root / "mutation.json"
            medium = root / "medium.json"
            out = root / "advisor.json"
            governance.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "kpis": {"strict_non_pass_rate": 0.6}, "risks": ["x"]}),
                encoding="utf-8",
            )
            mutation.write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "latest_match_rate": 0.95,
                        "latest_gate_pass_rate": 0.96,
                        "compare_decision": "FAIL",
                        "trend_status": "NEEDS_REVIEW",
                    }
                ),
                encoding="utf-8",
            )
            medium.write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "pass_rate": 0.8,
                        "mismatch_case_count": 2,
                        "trend_delta_pass_rate": -0.2,
                        "advisor_decision": "TIGHTEN",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_advisor",
                    "--governance-snapshot",
                    str(governance),
                    "--mutation-dashboard",
                    str(mutation),
                    "--medium-dashboard",
                    str(medium),
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
            reasons = advice.get("reasons", [])
            self.assertIn("mutation_compare_regressed", reasons)
            self.assertIn("medium_dashboard_advisor_tighten", reasons)
            patch = advice.get("threshold_patch", {})
            self.assertEqual(patch.get("require_min_top_score_margin"), 2)
            self.assertEqual(patch.get("require_min_explanation_quality"), 85)


if __name__ == "__main__":
    unittest.main()
