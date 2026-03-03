import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetJointMoatStrengthHistoryLedgerV1Tests(unittest.TestCase):
    def test_history_ledger_appends(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gate = root / "gate.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            gate.write_text(
                json.dumps({"status": "PASS", "moat_strength_score": 84.0, "moat_strength_grade": "B", "hard_fail_count": 0, "warning_count": 1}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_joint_moat_strength_history_ledger_v1",
                    "--joint-moat-strength-summary",
                    str(gate),
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
                    "gateforge.dataset_joint_moat_strength_history_ledger_v1",
                    "--joint-moat-strength-summary",
                    str(root / "missing_gate.json"),
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
