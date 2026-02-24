import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MutationHistoryTrendTests(unittest.TestCase):
    def test_trend_detects_regression(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            current.write_text(json.dumps({"latest_match_rate": 0.9, "latest_gate_pass_rate": 0.8}), encoding="utf-8")
            previous.write_text(json.dumps({"latest_match_rate": 1.0, "latest_gate_pass_rate": 0.9}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.mutation_history_trend",
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
            self.assertIn("match_rate_regression_detected", alerts)


if __name__ == "__main__":
    unittest.main()
