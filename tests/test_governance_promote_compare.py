import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePromoteCompareTests(unittest.TestCase):
    def test_promote_compare_selects_best_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            out = root / "summary.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": [],
                        "kpis": {
                            "recommended_profile": "default",
                            "strict_non_pass_rate": 0.0,
                            "strict_downgrade_rate": 0.0,
                            "review_recovery_rate": 0.9,
                            "fail_rate": 0.1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_compare",
                    "--snapshot",
                    str(snapshot),
                    "--profiles",
                    "default",
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
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("best_profile"), "default")
            self.assertIn(payload.get("best_reason"), {"recommended_profile_preferred_within_top_score", "best_decision_score"})

    def test_promote_compare_fails_when_all_profiles_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            out = root / "summary.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "FAIL",
                        "risks": ["ci_matrix_failed"],
                        "kpis": {
                            "recommended_profile": "default",
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_compare",
                    "--snapshot",
                    str(snapshot),
                    "--profiles",
                    "default",
                    "industrial_strict",
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
            self.assertEqual(len(payload.get("profile_results", [])), 2)


if __name__ == "__main__":
    unittest.main()
