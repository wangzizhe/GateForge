import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelIntakeBacklogPrioritizerV1Tests(unittest.TestCase):
    def test_backlog_prioritizer_generates_items(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "ledger.json"
            lic = root / "lic.json"
            yld = root / "yield.json"
            matrix = root / "matrix.json"
            out = root / "summary.json"
            backlog = root / "backlog.json"
            ledger.write_text(json.dumps({"records": [{"model_id": "m1", "decision": "REJECT", "reasons": ["license_not_allowed"]}]}), encoding="utf-8")
            lic.write_text(json.dumps({"status": "NEEDS_REVIEW", "alerts": ["disallowed_license_detected"]}), encoding="utf-8")
            yld.write_text(json.dumps({"status": "NEEDS_REVIEW", "alerts": ["yield_per_accepted_model_below_threshold"]}), encoding="utf-8")
            matrix.write_text(json.dumps({"missing_cells": [{"model_scale": "large", "failure_type": "simulate_error", "missing_mutations": 1}]}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_backlog_prioritizer_v1",
                    "--real-model-intake-ledger",
                    str(ledger),
                    "--real-model-license-compliance-summary",
                    str(lic),
                    "--real-model-failure-yield-summary",
                    str(yld),
                    "--mutation-execution-matrix-summary",
                    str(matrix),
                    "--backlog-out",
                    str(backlog),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(int(summary.get("backlog_item_count", 0)), 1)
            payload = json.loads(backlog.read_text(encoding="utf-8"))
            first = (payload.get("items") or [{}])[0]
            self.assertIn("owner_lane", first)
            self.assertIn("suggested_sla_days", first)

    def test_backlog_prioritizer_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_intake_backlog_prioritizer_v1",
                    "--real-model-intake-ledger",
                    str(root / "missing_ledger.json"),
                    "--real-model-license-compliance-summary",
                    str(root / "missing_lic.json"),
                    "--real-model-failure-yield-summary",
                    str(root / "missing_yld.json"),
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
