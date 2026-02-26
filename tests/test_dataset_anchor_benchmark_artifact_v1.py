import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetAnchorBenchmarkArtifactV1Tests(unittest.TestCase):
    def test_anchor_artifact_computes_score(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            gate = root / "gate.json"
            proof = root / "proof.json"
            out = root / "summary.json"

            baseline.write_text(json.dumps({"status": "PASS", "baseline_id": "x", "total_selected_cases": 10}), encoding="utf-8")
            gate.write_text(json.dumps({"gate_result": "PASS"}), encoding="utf-8")
            proof.write_text(json.dumps({"proof_score": 80.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_benchmark_artifact_v1",
                    "--failure-baseline-pack-summary",
                    str(baseline),
                    "--failure-distribution-quality-gate",
                    str(gate),
                    "--external-proof-score",
                    str(proof),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertIsInstance(summary.get("anchor_score"), float)

    def test_anchor_artifact_fails_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_benchmark_artifact_v1",
                    "--failure-baseline-pack-summary",
                    str(root / "missing1.json"),
                    "--failure-distribution-quality-gate",
                    str(root / "missing2.json"),
                    "--external-proof-score",
                    str(root / "missing3.json"),
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
