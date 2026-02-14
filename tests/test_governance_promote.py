import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePromoteTests(unittest.TestCase):
    def test_promote_pass_under_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            out = root / "promote.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": [],
                        "kpis": {
                            "strict_non_pass_rate": 0.1,
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
                    "gateforge.governance_promote",
                    "--snapshot",
                    str(snapshot),
                    "--profile",
                    "default",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "PASS")

    def test_promote_needs_review_under_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            out = root / "promote.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": [],
                        "kpis": {
                            "strict_non_pass_rate": 0.6,
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
                    "gateforge.governance_promote",
                    "--snapshot",
                    str(snapshot),
                    "--profile",
                    "default",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("decision"), "NEEDS_REVIEW")
            self.assertTrue(payload.get("reasons"))

    def test_promote_fail_under_industrial_strict(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            out = root / "promote.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "risks": ["strict_profile_downgrade_detected"],
                        "kpis": {
                            "strict_non_pass_rate": 0.3,
                            "strict_downgrade_rate": 0.2,
                            "review_recovery_rate": 0.5,
                            "fail_rate": 0.2,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote",
                    "--snapshot",
                    str(snapshot),
                    "--profile",
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
            self.assertEqual(payload.get("decision"), "FAIL")


if __name__ == "__main__":
    unittest.main()
