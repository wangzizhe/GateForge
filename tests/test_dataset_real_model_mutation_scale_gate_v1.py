import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelMutationScaleGateV1Tests(unittest.TestCase):
    def test_scale_gate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            discovery = root / "discovery.json"
            pipeline = root / "pipeline.json"
            runner = root / "runner.json"
            pack = root / "pack.json"
            real_run = root / "realrun.json"
            out = root / "summary.json"

            discovery.write_text(json.dumps({"total_candidates": 8}), encoding="utf-8")
            pipeline.write_text(json.dumps({"accepted_count": 6}), encoding="utf-8")
            runner.write_text(json.dumps({"accepted_count": 5, "accepted_large_count": 2}), encoding="utf-8")
            pack.write_text(json.dumps({"total_mutations": 30}), encoding="utf-8")
            real_run.write_text(json.dumps({"executed_count": 24}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_scale_gate_v1",
                    "--asset-discovery-summary",
                    str(discovery),
                    "--intake-pipeline-summary",
                    str(pipeline),
                    "--intake-runner-summary",
                    str(runner),
                    "--mutation-pack-summary",
                    str(pack),
                    "--mutation-real-runner-summary",
                    str(real_run),
                    "--min-reproducible-mutations",
                    "20",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")

    def test_scale_gate_fail_on_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_scale_gate_v1",
                    "--asset-discovery-summary",
                    str(root / "m1.json"),
                    "--intake-pipeline-summary",
                    str(root / "m2.json"),
                    "--intake-runner-summary",
                    str(root / "m3.json"),
                    "--mutation-pack-summary",
                    str(root / "m4.json"),
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
