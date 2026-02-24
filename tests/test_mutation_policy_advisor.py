import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MutationPolicyAdvisorTests(unittest.TestCase):
    def test_advisor_marks_stable_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dashboard = root / "dashboard.json"
            out = root / "advisor.json"
            dashboard.write_text(
                json.dumps(
                    {
                        "latest_match_rate": 1.0,
                        "latest_gate_pass_rate": 1.0,
                        "trend_status": "PASS",
                        "compare_decision": "PASS",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.mutation_policy_advisor", "--dashboard", str(dashboard), "--out", str(out)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("suggested_policy_profile"), "default")
            self.assertIn("mutation_signals_stable", advice.get("reasons", []))

    def test_advisor_tightens_on_regression_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dashboard = root / "dashboard.json"
            out = root / "advisor.json"
            dashboard.write_text(
                json.dumps(
                    {
                        "latest_match_rate": 0.9,
                        "latest_gate_pass_rate": 0.92,
                        "trend_status": "NEEDS_REVIEW",
                        "compare_decision": "FAIL",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.mutation_policy_advisor", "--dashboard", str(dashboard), "--out", str(out)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("suggested_policy_profile"), "industrial_strict")
            reasons = advice.get("reasons", [])
            self.assertIn("mutation_pack_compare_regressed", reasons)
            patch = advice.get("threshold_patch", {})
            self.assertEqual(patch.get("require_min_top_score_margin"), 2)
            self.assertEqual(patch.get("require_min_explanation_quality"), 85)


if __name__ == "__main__":
    unittest.main()
