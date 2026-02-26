import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureDistributionQualityGateV1Tests(unittest.TestCase):
    def test_quality_gate_pass_on_good_mix(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack = root / "pack.json"
            out = root / "summary.json"
            pack.write_text(
                json.dumps(
                    {
                        "selected_cases": [
                            {"model_scale": "small", "failure_type": "a"},
                            {"model_scale": "medium", "failure_type": "b"},
                            {"model_scale": "medium", "failure_type": "c"},
                            {"model_scale": "large", "failure_type": "d"},
                            {"model_scale": "large", "failure_type": "e"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_quality_gate_v1",
                    "--failure-baseline-pack",
                    str(pack),
                    "--min-medium-share-pct",
                    "20",
                    "--min-large-share-pct",
                    "20",
                    "--min-unique-failure-types",
                    "5",
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

    def test_quality_gate_fail_when_pack_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_quality_gate_v1",
                    "--failure-baseline-pack",
                    str(root / "missing.json"),
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
