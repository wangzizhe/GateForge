import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPromotionEffectivenessHistoryTests(unittest.TestCase):
    def test_history_summary_builds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            eff = root / "effectiveness.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            eff.write_text(json.dumps({"decision": "KEEP", "reasons": []}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_effectiveness_history",
                    "--record",
                    str(eff),
                    "--ledger",
                    str(ledger),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_records"), 1)
            self.assertEqual(payload.get("latest_decision"), "KEEP")

    def test_history_trend_detects_regression(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(
                json.dumps({"keep_rate": 0.4, "needs_review_rate": 0.4, "rollback_review_rate": 0.2}),
                encoding="utf-8",
            )
            previous.write_text(
                json.dumps({"keep_rate": 0.8, "needs_review_rate": 0.1, "rollback_review_rate": 0.1}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_effectiveness_history_trend",
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
            alerts = (payload.get("trend") or {}).get("alerts") or []
            self.assertIn("keep_rate_decreasing", alerts)
            self.assertIn("needs_review_rate_increasing", alerts)


if __name__ == "__main__":
    unittest.main()
