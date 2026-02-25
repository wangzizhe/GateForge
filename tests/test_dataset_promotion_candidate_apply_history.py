import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPromotionCandidateApplyHistoryTests(unittest.TestCase):
    def test_history_summary_builds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            apply_summary = root / "apply.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            apply_summary.write_text(
                json.dumps({"final_status": "PASS", "apply_action": "applied", "decision": "PROMOTE", "reasons": []}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_candidate_apply_history",
                    "--record",
                    str(apply_summary),
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
            self.assertEqual(payload.get("total_records"), 1)
            self.assertEqual(payload.get("latest_final_status"), "PASS")


if __name__ == "__main__":
    unittest.main()
