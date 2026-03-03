import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationSelectionHistoryLedgerV1Tests(unittest.TestCase):
    def test_history_ledger_appends(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            guard = root / "guard.json"
            pack = root / "pack.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            plan.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "selected_models": 12,
                        "selected_large_ratio_pct": 40.0,
                        "selected_families": 4,
                        "selected_source_buckets": 3,
                        "max_family_share_pct": 35.0,
                    }
                ),
                encoding="utf-8",
            )
            guard.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            pack.write_text(json.dumps({"total_mutations": 120}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_selection_history_ledger_v1",
                    "--selection-plan-summary",
                    str(plan),
                    "--selection-balance-guard-summary",
                    str(guard),
                    "--mutation-pack-summary",
                    str(pack),
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
                    "gateforge.dataset_mutation_selection_history_ledger_v1",
                    "--selection-plan-summary",
                    str(root / "missing_plan.json"),
                    "--selection-balance-guard-summary",
                    str(root / "missing_guard.json"),
                    "--mutation-pack-summary",
                    str(root / "missing_pack.json"),
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
