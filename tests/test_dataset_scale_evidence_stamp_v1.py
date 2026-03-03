import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetScaleEvidenceStampV1Tests(unittest.TestCase):
    def test_evidence_stamp_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pool = root / "pool.json"
            inv = root / "inv.json"
            gate = root / "gate.json"
            out = root / "summary.json"
            pool.write_text(json.dumps({"existing_file_ratio": 1.0, "nontrivial_model_ratio": 0.9}), encoding="utf-8")
            inv.write_text(json.dumps({"existing_file_ratio": 1.0, "execution_coverage_ratio": 1.0}), encoding="utf-8")
            gate.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_evidence_stamp_v1",
                    "--real-model-pool-audit-summary",
                    str(pool),
                    "--mutation-artifact-inventory-summary",
                    str(inv),
                    "--scale-gate-summary",
                    str(gate),
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
            self.assertGreaterEqual(float(payload.get("evidence_score", 0.0)), 0.0)

    def test_evidence_stamp_fail_when_required_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_evidence_stamp_v1",
                    "--real-model-pool-audit-summary",
                    str(root / "missing_pool.json"),
                    "--mutation-artifact-inventory-summary",
                    str(root / "missing_inv.json"),
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
