import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatDefensibilityHistoryV1Tests(unittest.TestCase):
    def test_history_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r1 = root / "r1.json"
            r2 = root / "r2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            r1.write_text(json.dumps({"status": "PASS", "moat_defensibility_score": 80.0, "key_alert_count": 0}), encoding="utf-8")
            r2.write_text(json.dumps({"status": "NEEDS_REVIEW", "moat_defensibility_score": 70.0, "key_alert_count": 2}), encoding="utf-8")

            p1 = subprocess.run([sys.executable, "-m", "gateforge.dataset_moat_defensibility_history_v1", "--moat-defensibility-report-summary", str(r1), "--ledger", str(ledger), "--out", str(root / "s1.json")], capture_output=True, text=True, check=False)
            self.assertEqual(p1.returncode, 0, msg=p1.stderr or p1.stdout)
            p2 = subprocess.run([sys.executable, "-m", "gateforge.dataset_moat_defensibility_history_v1", "--moat-defensibility-report-summary", str(r2), "--ledger", str(ledger), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(p2.returncode, 0, msg=p2.stderr or p2.stdout)

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(int(payload.get("total_records", 0)), 2)
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")

    def test_history_fail_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_defensibility_history_v1",
                    "--moat-defensibility-report-summary",
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
