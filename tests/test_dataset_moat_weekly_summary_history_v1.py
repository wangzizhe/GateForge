import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatWeeklySummaryHistoryV1Tests(unittest.TestCase):
    def test_history_appends_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "w1.json"
            r2 = root / "w2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"

            r1.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "week_tag": "2026-W09",
                        "kpis": {
                            "real_model_count": 10,
                            "reproducible_mutation_count": 30,
                            "failure_distribution_stability_score": 88.0,
                            "gateforge_vs_plain_ci_advantage_score": 8,
                        },
                    }
                ),
                encoding="utf-8",
            )
            r2.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "week_tag": "2026-W10",
                        "kpis": {
                            "real_model_count": 12,
                            "reproducible_mutation_count": 36,
                            "failure_distribution_stability_score": 90.0,
                            "gateforge_vs_plain_ci_advantage_score": 10,
                        },
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_weekly_summary_history_v1",
                    "--record",
                    str(r1),
                    "--record",
                    str(r2),
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
            self.assertEqual(int(payload.get("total_records", 0)), 2)
            self.assertIsInstance(payload.get("avg_stability_score"), (int, float))


if __name__ == "__main__":
    unittest.main()
