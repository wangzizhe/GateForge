import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeModelAuthenticityHistoryLedgerV1Tests(unittest.TestCase):
    def test_history_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            summary = root / "large_auth.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            summary.write_text(
                json.dumps({"status": "PASS", "large_model_authenticity_score": 72.0, "failed_gate_count": 0, "critical_failed_gate_count": 0}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_authenticity_history_ledger_v1",
                    "--large-model-authenticity-summary",
                    str(summary),
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
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_authenticity_history_ledger_v1",
                    "--large-model-authenticity-summary",
                    str(root / "missing.json"),
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
