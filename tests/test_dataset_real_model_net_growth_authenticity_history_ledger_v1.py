import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelNetGrowthAuthenticityHistoryLedgerV1Tests(unittest.TestCase):
    def test_history_ledger_appends(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gate = root / "gate.json"
            canonical = root / "canonical.json"
            runner = root / "runner.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            gate.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "canonical_new_models": 12,
                        "net_new_unique_models": 10,
                        "true_growth_ratio_pct": 83.33,
                        "suspected_duplicate_ratio_pct": 16.67,
                    }
                ),
                encoding="utf-8",
            )
            canonical.write_text(json.dumps({"canonical_total_models": 300}), encoding="utf-8")
            runner.write_text(json.dumps({"accepted_count": 240}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_net_growth_authenticity_history_ledger_v1",
                    "--net-growth-authenticity-summary",
                    str(gate),
                    "--canonical-registry-summary",
                    str(canonical),
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

    def test_history_ledger_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_net_growth_authenticity_history_ledger_v1",
                    "--net-growth-authenticity-summary",
                    str(root / "missing_gate.json"),
                    "--canonical-registry-summary",
                    str(root / "missing_canonical.json"),
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
