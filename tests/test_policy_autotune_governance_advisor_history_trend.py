import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneGovernanceAdvisorHistoryTrendTests(unittest.TestCase):
    def test_trend_detects_tighten_increase(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(
                json.dumps({"tighten_rate": 0.8, "rollback_review_rate": 0.2, "pairwise_patch_rate": 0.5}),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps({"tighten_rate": 0.2, "rollback_review_rate": 0.0, "pairwise_patch_rate": 0.0}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_governance_advisor_history_trend",
                    "--current",
                    str(current),
                    "--previous",
                    str(previous),
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
            alerts = (payload.get("trend") or {}).get("alerts", [])
            self.assertIn("tighten_rate_increasing", alerts)
            self.assertIn("pairwise_patch_rate_increasing", alerts)


if __name__ == "__main__":
    unittest.main()
