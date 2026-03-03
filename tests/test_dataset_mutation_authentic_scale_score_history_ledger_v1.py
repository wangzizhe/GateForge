import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationAuthenticScaleScoreHistoryLedgerV1Tests(unittest.TestCase):
    def test_history_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            current = root / "score.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            current.write_text(
                json.dumps({"status": "PASS", "authentic_scale_score": 81.0, "authentic_scale_grade": "B", "warning_count": 0}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_authentic_scale_score_history_ledger_v1",
                    "--mutation-authentic-scale-score-summary",
                    str(current),
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
            self.assertEqual(payload.get("status"), "PASS")

    def test_history_fail_on_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_authentic_scale_score_history_ledger_v1",
                    "--mutation-authentic-scale-score-summary",
                    str(root / "missing.json"),
                    "--ledger",
                    str(ledger),
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
