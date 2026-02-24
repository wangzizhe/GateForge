import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RuntimeLedgerHistoryTests(unittest.TestCase):
    def _write_summary(self, path: Path, pass_rate: float, fail_rate: float, review_rate: float, source_counts: dict) -> None:
        path.write_text(
            json.dumps(
                {
                    "total_records": 10,
                    "kpis": {
                        "pass_rate": pass_rate,
                        "fail_rate": fail_rate,
                        "needs_review_rate": review_rate,
                    },
                    "source_counts": source_counts,
                }
            ),
            encoding="utf-8",
        )

    def test_history_aggregates_runtime_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            s1 = root / "s1.json"
            s2 = root / "s2.json"
            ledger = root / "history.jsonl"
            out = root / "history_summary.json"
            self._write_summary(s1, pass_rate=0.9, fail_rate=0.05, review_rate=0.05, source_counts={"run": 5, "autopilot": 5})
            self._write_summary(s2, pass_rate=0.5, fail_rate=0.35, review_rate=0.15, source_counts={"run": 2, "autopilot": 8})
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.runtime_ledger_history",
                    "--record",
                    str(s1),
                    "--record",
                    str(s2),
                    "--ledger",
                    str(ledger),
                    "--out",
                    str(out),
                    "--fail-rate-alert-threshold",
                    "0.3",
                    "--needs-review-alert-threshold",
                    "0.1",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_records"), 2)
            self.assertEqual(payload.get("latest_fail_rate"), 0.35)
            self.assertEqual(payload.get("source_counts", {}).get("run"), 7)
            self.assertEqual(payload.get("source_counts", {}).get("autopilot"), 13)
            alerts = payload.get("alerts", [])
            self.assertIn("latest_fail_rate_high", alerts)
            self.assertIn("latest_needs_review_rate_high", alerts)

    def test_history_from_existing_ledger_without_new_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "history.jsonl"
            out = root / "history_summary.json"
            ledger.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "total_records": 10,
                                "pass_rate": 1.0,
                                "fail_rate": 0.0,
                                "needs_review_rate": 0.0,
                                "source_counts": {"run": 10},
                            }
                        ),
                        json.dumps(
                            {
                                "total_records": 11,
                                "pass_rate": 0.91,
                                "fail_rate": 0.09,
                                "needs_review_rate": 0.0,
                                "source_counts": {"run": 11},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.runtime_ledger_history",
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
