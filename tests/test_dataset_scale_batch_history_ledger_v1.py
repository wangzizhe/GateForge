import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetScaleBatchHistoryLedgerV1Tests(unittest.TestCase):
    def test_history_ledger_appends_and_summarizes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rec1 = root / "r1.json"
            rec2 = root / "r2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"

            rec1.write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "scale_gate_status": "PASS",
                        "hard_moat_gates_status": "PASS",
                        "accepted_models": 10,
                        "generated_mutations": 100,
                        "reproducible_mutations": 90,
                        "canonical_total_models": 500,
                        "canonical_net_growth_models": 12,
                        "hard_moat_hardness_score": 78.0,
                    }
                ),
                encoding="utf-8",
            )
            rec2.write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "scale_gate_status": "PASS",
                        "hard_moat_gates_status": "NEEDS_REVIEW",
                        "accepted_models": 12,
                        "generated_mutations": 130,
                        "reproducible_mutations": 120,
                        "canonical_total_models": 512,
                        "canonical_net_growth_models": 12,
                        "hard_moat_hardness_score": 80.0,
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_batch_history_ledger_v1",
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
            self.assertEqual(int(payload.get("delta_canonical_total_models", 0)), 12)


if __name__ == "__main__":
    unittest.main()
