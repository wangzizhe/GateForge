import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeModelExecutableTruthHistoryLedgerV1Tests(unittest.TestCase):
    def test_history_ledger_appends(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gate = root / "gate.json"
            runner = root / "runner.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            gate.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "large_model_count": 20,
                        "large_executable_real_count": 16,
                        "large_executable_real_rate_pct": 80.0,
                        "large_model_check_pass_rate_pct": 95.0,
                    }
                ),
                encoding="utf-8",
            )
            runner.write_text(json.dumps({"accepted_large_count": 18}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_executable_truth_history_ledger_v1",
                    "--large-model-executable-truth-summary",
                    str(gate),
                    "--intake-runner-summary",
                    str(runner),
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

    def test_history_ledger_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_executable_truth_history_ledger_v1",
                    "--large-model-executable-truth-summary",
                    str(root / "missing_gate.json"),
                    "--intake-runner-summary",
                    str(root / "missing_runner.json"),
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
