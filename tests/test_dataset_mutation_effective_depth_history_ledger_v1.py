import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationEffectiveDepthHistoryLedgerV1Tests(unittest.TestCase):
    def test_history_ledger_appends(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            guard = root / "guard.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            guard.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "tracked_models": 10,
                        "large_models": 4,
                        "total_effective_mutations": 200,
                        "p10_effective_mutations_per_model": 2.0,
                        "models_meeting_effective_depth_ratio_pct": 80.0,
                        "large_models_meeting_effective_depth_ratio_pct": 75.0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_effective_depth_history_ledger_v1",
                    "--mutation-effective-depth-summary",
                    str(guard),
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
            self.assertEqual(int(payload.get("total_records", 0)), 1)

    def test_history_ledger_fail_when_input_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_effective_depth_history_ledger_v1",
                    "--mutation-effective-depth-summary",
                    str(root / "missing_guard.json"),
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
