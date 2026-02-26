import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetAnchorBenchmarkPackV2Tests(unittest.TestCase):
    def test_anchor_pack_v2_computes_score(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            gate = root / "gate.json"
            mutation = root / "mutation.json"
            stability = root / "stability.json"
            ingest = root / "ingest.json"
            out = root / "summary.json"

            baseline.write_text(json.dumps({"status": "PASS", "baseline_id": "b1"}), encoding="utf-8")
            gate.write_text(json.dumps({"gate_result": "PASS"}), encoding="utf-8")
            mutation.write_text(json.dumps({"total_mutations": 20, "unique_failure_types": 4}), encoding="utf-8")
            stability.write_text(json.dumps({"stability_ratio_pct": 90.0}), encoding="utf-8")
            ingest.write_text(json.dumps({"ingested_cases": 6}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_benchmark_pack_v2",
                    "--failure-baseline-pack-summary",
                    str(baseline),
                    "--failure-distribution-quality-gate",
                    str(gate),
                    "--mutation-factory-summary",
                    str(mutation),
                    "--repro-stability-summary",
                    str(stability),
                    "--failure-corpus-ingest-summary",
                    str(ingest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIsInstance(payload.get("anchor_pack_score"), float)

    def test_anchor_pack_v2_fails_without_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_benchmark_pack_v2",
                    "--failure-baseline-pack-summary",
                    str(root / "missing1.json"),
                    "--failure-distribution-quality-gate",
                    str(root / "missing2.json"),
                    "--mutation-factory-summary",
                    str(root / "missing3.json"),
                    "--repro-stability-summary",
                    str(root / "missing4.json"),
                    "--failure-corpus-ingest-summary",
                    str(root / "missing5.json"),
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
