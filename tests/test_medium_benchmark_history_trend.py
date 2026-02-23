import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class MediumBenchmarkHistoryTrendTests(unittest.TestCase):
    def _write_summary(self, path: Path, total_records: int, pass_rate: float, mismatch_total: int) -> None:
        path.write_text(
            json.dumps(
                {
                    "total_records": total_records,
                    "latest_pack_id": "medium_pack_v1",
                    "latest_pass_rate": pass_rate,
                    "mismatch_case_total": mismatch_total,
                }
            ),
            encoding="utf-8",
        )

    def test_trend_detects_pass_rate_regression_and_mismatch_growth(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            previous = root / "previous.json"
            out = root / "trend.json"
            self._write_summary(previous, total_records=2, pass_rate=1.0, mismatch_total=0)
            self._write_summary(current, total_records=4, pass_rate=0.75, mismatch_total=3)
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_history_trend",
                    "--summary",
                    str(current),
                    "--previous-summary",
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
            trend = payload.get("trend", {})
            self.assertEqual(trend.get("delta_total_records"), 2)
            self.assertAlmostEqual(trend.get("delta_pass_rate"), -0.25)
            self.assertEqual(trend.get("delta_mismatch_case_total"), 3)
            alerts = payload.get("trend_alerts", [])
            self.assertIn("pass_rate_regression_detected", alerts)
            self.assertIn("mismatch_case_growth_detected", alerts)

    def test_trend_without_previous_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "current.json"
            out = root / "trend.json"
            self._write_summary(current, total_records=1, pass_rate=1.0, mismatch_total=0)
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_history_trend",
                    "--summary",
                    str(current),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            trend = payload.get("trend", {})
            self.assertEqual(trend.get("delta_total_records"), 1)
            self.assertAlmostEqual(trend.get("delta_pass_rate"), 1.0)
            self.assertEqual(payload.get("trend_alerts"), [])


if __name__ == "__main__":
    unittest.main()
