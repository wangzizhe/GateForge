import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelMutationFreezeHistoryLedgerV1Tests(unittest.TestCase):
    def test_freeze_history_ledger_appends_and_summarizes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rec1 = root / "freeze1.json"
            rec2 = root / "freeze2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"

            rec1.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "freeze_id": "f1",
                        "week_tag": "2026-W10",
                        "accepted_models": 100,
                        "generated_mutations": 1000,
                        "reproducible_mutations": 990,
                        "canonical_net_growth_models": 5,
                        "validation_type_match_rate_pct": 70.0,
                        "distribution_guard_status": "PASS",
                    }
                ),
                encoding="utf-8",
            )
            rec2.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "freeze_id": "f2",
                        "week_tag": "2026-W11",
                        "accepted_models": 110,
                        "generated_mutations": 1200,
                        "reproducible_mutations": 1180,
                        "canonical_net_growth_models": 7,
                        "validation_type_match_rate_pct": 72.5,
                        "distribution_guard_status": "PASS",
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_freeze_history_ledger_v1",
                    "--record",
                    str(rec1),
                    "--record",
                    str(rec2),
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
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(payload.get("total_records", 0)), 2)
            self.assertGreater(float(payload.get("avg_generated_mutations", 0.0)), 1000.0)

    def test_freeze_history_ledger_fail_without_valid_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_freeze_history_ledger_v1",
                    "--record",
                    str(root / "missing.json"),
                    "--ledger",
                    str(root / "history.jsonl"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
