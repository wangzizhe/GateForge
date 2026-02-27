import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelFailureYieldTrackerV1Tests(unittest.TestCase):
    def test_yield_tracker_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "ledger.json"
            matrix = root / "matrix.json"
            out = root / "summary.json"
            ledger.write_text(json.dumps({"records": [{"model_id": "m1", "decision": "ACCEPT"}]}), encoding="utf-8")
            matrix.write_text(json.dumps({"executed_mutations": 2, "total_mutations": 2, "matrix_execution_ratio_pct": 100}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_failure_yield_tracker_v1",
                    "--real-model-intake-ledger",
                    str(ledger),
                    "--mutation-execution-matrix-summary",
                    str(matrix),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")

    def test_yield_tracker_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_failure_yield_tracker_v1",
                    "--real-model-intake-ledger",
                    str(root / "missing_ledger.json"),
                    "--mutation-execution-matrix-summary",
                    str(root / "missing_matrix.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
