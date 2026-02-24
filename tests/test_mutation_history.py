import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MutationHistoryTests(unittest.TestCase):
    def test_history_summary_from_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            m1 = root / "m1.json"
            m2 = root / "m2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            m1.write_text(
                json.dumps({"pack_id": "p0", "pack_version": "v0", "total_cases": 8, "expected_vs_actual_match_rate": 1.0, "gate_pass_rate": 1.0}),
                encoding="utf-8",
            )
            m2.write_text(
                json.dumps({"pack_id": "p1", "pack_version": "v1", "total_cases": 24, "expected_vs_actual_match_rate": 0.96, "gate_pass_rate": 0.97}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.mutation_history",
                    "--record",
                    str(m1),
                    "--record",
                    str(m2),
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
            self.assertEqual(payload.get("total_records"), 2)
            self.assertEqual(payload.get("latest_pack_id"), "p1")
            self.assertIsInstance(payload.get("avg_match_rate"), float)


if __name__ == "__main__":
    unittest.main()
