import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class MediumBenchmarkHistoryTests(unittest.TestCase):
    def _write_summary(self, path: Path, pass_rate: float, mismatch_case_count: int, fail_count: int) -> None:
        path.write_text(
            json.dumps(
                {
                    "pack_id": "medium_pack_v1",
                    "total_cases": 12,
                    "pass_count": 12 - fail_count,
                    "fail_count": fail_count,
                    "pass_rate": pass_rate,
                    "mismatch_case_count": mismatch_case_count,
                }
            ),
            encoding="utf-8",
        )

    def test_history_aggregates_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "s1.json"
            r2 = root / "s2.json"
            ledger = root / "history.jsonl"
            out = root / "history_summary.json"
            self._write_summary(r1, 1.0, 0, 0)
            self._write_summary(r2, 0.75, 3, 3)
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_history",
                    "--record",
                    str(r1),
                    "--record",
                    str(r2),
                    "--ledger",
                    str(ledger),
                    "--out",
                    str(out),
                    "--min-pass-rate",
                    "0.9",
                    "--mismatch-threshold",
                    "1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_records"), 2)
            self.assertEqual(payload.get("latest_pass_rate"), 0.75)
            self.assertEqual(payload.get("mismatch_case_total"), 3)
            alerts = payload.get("alerts", [])
            self.assertIn("latest_pass_rate_low", alerts)
            self.assertIn("mismatch_case_volume_high", alerts)
            self.assertIn("historical_fail_detected", alerts)

    def test_history_reads_existing_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "history.jsonl"
            out = root / "history_summary.json"
            ledger.write_text(
                "\n".join(
                    [
                        json.dumps({"pack_id": "medium_pack_v1", "pass_rate": 1.0, "mismatch_case_count": 0, "fail_count": 0}),
                        json.dumps({"pack_id": "medium_pack_v1", "pass_rate": 1.0, "mismatch_case_count": 0, "fail_count": 0}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.medium_benchmark_history",
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
            self.assertEqual(payload.get("ingested_count"), 0)
            self.assertEqual(payload.get("total_records"), 2)
            self.assertEqual(payload.get("alerts"), [])


if __name__ == "__main__":
    unittest.main()
