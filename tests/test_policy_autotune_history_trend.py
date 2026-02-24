import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PolicyAutotuneHistoryTrendTests(unittest.TestCase):
    def test_trend_detects_strict_increase(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(json.dumps({"strict_suggestion_rate": 0.7, "avg_confidence": 0.65}), encoding="utf-8")
            previous.write_text(json.dumps({"strict_suggestion_rate": 0.2, "avg_confidence": 0.8}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.policy_autotune_history_trend",
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
            self.assertIn("strict_suggestion_rate_increasing", alerts)


if __name__ == "__main__":
    unittest.main()
