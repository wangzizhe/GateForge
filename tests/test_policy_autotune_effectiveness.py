import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneEffectivenessTests(unittest.TestCase):
    def test_effectiveness_detects_improvement(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            flow = root / "flow.json"
            out = root / "effectiveness.json"
            flow.write_text(
                json.dumps(
                    {
                        "baseline": {"compare_status": "NEEDS_REVIEW", "apply_status": "NEEDS_REVIEW"},
                        "tuned": {"compare_status": "PASS", "apply_status": "PASS"},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_effectiveness",
                    "--flow-summary",
                    str(flow),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "IMPROVED")
            self.assertGreater(payload.get("delta_apply_score", 0), 0)

    def test_effectiveness_detects_quality_regression_when_status_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            flow = root / "flow.json"
            baseline_compare = root / "baseline_compare.json"
            tuned_compare = root / "tuned_compare.json"
            out = root / "effectiveness.json"
            baseline_compare.write_text(
                json.dumps(
                    {
                        "top_score_margin": 4,
                        "explanation_completeness": 95,
                        "decision_explanation_leaderboard": [{"pairwise_net_margin": 6}],
                    }
                ),
                encoding="utf-8",
            )
            tuned_compare.write_text(
                json.dumps(
                    {
                        "top_score_margin": 2,
                        "explanation_completeness": 90,
                        "decision_explanation_leaderboard": [{"pairwise_net_margin": 2}],
                    }
                ),
                encoding="utf-8",
            )
            flow.write_text(
                json.dumps(
                    {
                        "baseline": {
                            "compare_status": "PASS",
                            "apply_status": "PASS",
                            "compare_path": str(baseline_compare),
                        },
                        "tuned": {
                            "compare_status": "PASS",
                            "apply_status": "PASS",
                            "compare_path": str(tuned_compare),
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_effectiveness",
                    "--flow-summary",
                    str(flow),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "REGRESSED")
            self.assertIn("compare_quality_regressed", payload.get("reasons", []))
            self.assertEqual(payload.get("delta_top_score_margin"), -2)
            self.assertEqual(payload.get("delta_explanation_completeness"), -5)
            self.assertEqual(payload.get("delta_pairwise_net_margin"), -4)


if __name__ == "__main__":
    unittest.main()
