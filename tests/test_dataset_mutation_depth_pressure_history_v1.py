import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationDepthPressureHistoryV1Tests(unittest.TestCase):
    def test_history_aggregates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            b1 = root / "b1.json"
            b2 = root / "b2.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            b1.write_text(json.dumps({"status": "PASS", "mutation_depth_pressure_index": 30.0, "high_risk_gap_count": 0, "missing_recipe_count": 0}), encoding="utf-8")
            b2.write_text(json.dumps({"status": "NEEDS_REVIEW", "mutation_depth_pressure_index": 40.0, "high_risk_gap_count": 1, "missing_recipe_count": 2}), encoding="utf-8")

            p1 = subprocess.run([sys.executable, "-m", "gateforge.dataset_mutation_depth_pressure_history_v1", "--mutation-depth-pressure-board-summary", str(b1), "--ledger", str(ledger), "--out", str(root / "s1.json")], capture_output=True, text=True, check=False)
            self.assertEqual(p1.returncode, 0, msg=p1.stderr or p1.stdout)
            p2 = subprocess.run([sys.executable, "-m", "gateforge.dataset_mutation_depth_pressure_history_v1", "--mutation-depth-pressure-board-summary", str(b2), "--ledger", str(ledger), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(p2.returncode, 0, msg=p2.stderr or p2.stdout)

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(int(payload.get("total_records", 0)), 2)
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")

    def test_history_fail_on_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_depth_pressure_history_v1",
                    "--mutation-depth-pressure-board-summary",
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
