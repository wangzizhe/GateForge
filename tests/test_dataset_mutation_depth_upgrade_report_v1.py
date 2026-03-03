import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationDepthUpgradeReportV1Tests(unittest.TestCase):
    def test_upgrade_report_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            baseline = root / "baseline.json"
            current = root / "current.json"
            out = root / "summary.json"

            baseline.write_text(
                json.dumps({"generated_mutations": 3780, "reproducible_mutations": 3780, "mutations_per_failure_type": 2}),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "generated_mutations": 7560,
                        "reproducible_mutations": 7560,
                        "mutations_per_failure_type": 4,
                        "accepted_models": 606,
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_depth_upgrade_report_v1",
                    "--current-scale-summary",
                    str(current),
                    "--baseline-scale-summary",
                    str(baseline),
                    "--target-mutations-per-failure-type",
                    "4",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("upgrade_status"), "UPGRADED")
            self.assertGreaterEqual(float(payload.get("generated_mutation_multiplier", 0.0)), 2.0)

    def test_upgrade_report_fail_when_current_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_depth_upgrade_report_v1",
                    "--current-scale-summary",
                    str(root / "missing_current.json"),
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
