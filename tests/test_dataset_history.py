import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetHistoryTests(unittest.TestCase):
    def test_dataset_history_aggregates_and_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record1 = root / "record1.json"
            record2 = root / "record2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            record1.write_text(
                json.dumps(
                    {
                        "build_deduplicated_cases": 6,
                        "quality_failure_case_rate": 0.1,
                        "freeze_status": "PASS",
                        "bundle_status": "PASS",
                    }
                ),
                encoding="utf-8",
            )
            record2.write_text(
                json.dumps(
                    {
                        "build_deduplicated_cases": 12,
                        "quality_failure_case_rate": 0.35,
                        "freeze_status": "PASS",
                        "bundle_status": "PASS",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_history",
                    "--record",
                    str(record1),
                    "--record",
                    str(record2),
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
            self.assertEqual(payload.get("total_records"), 2)
            self.assertEqual(payload.get("latest_deduplicated_cases"), 12)
            self.assertEqual(payload.get("latest_freeze_status"), "PASS")
            self.assertNotIn("latest_deduplicated_case_count_low", payload.get("alerts", []))

    def test_dataset_history_detects_low_latest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = root / "record.json"
            out = root / "summary.json"
            record.write_text(
                json.dumps(
                    {
                        "build_deduplicated_cases": 4,
                        "quality_failure_case_rate": 0.1,
                        "freeze_status": "NEEDS_REVIEW",
                        "bundle_status": "FAIL",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_history",
                    "--record",
                    str(record),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            alerts = payload.get("alerts", [])
            self.assertIn("latest_deduplicated_case_count_low", alerts)
            self.assertIn("latest_failure_case_rate_low", alerts)
            self.assertIn("latest_freeze_not_pass", alerts)
            self.assertIn("historical_dataset_bundle_fail", alerts)


if __name__ == "__main__":
    unittest.main()
