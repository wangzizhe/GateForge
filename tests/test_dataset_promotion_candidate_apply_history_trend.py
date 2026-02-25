import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPromotionCandidateApplyHistoryTrendTests(unittest.TestCase):
    def test_trend_detects_fail_rate_increase(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(json.dumps({"pass_rate": 0.4, "needs_review_rate": 0.3, "fail_rate": 0.3}), encoding="utf-8")
            previous.write_text(json.dumps({"pass_rate": 0.8, "needs_review_rate": 0.1, "fail_rate": 0.1}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_candidate_apply_history_trend",
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
            self.assertIn("apply_fail_rate_increasing", alerts)


if __name__ == "__main__":
    unittest.main()
