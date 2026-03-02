import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFailureDistributionBaselineFreezeV1Tests(unittest.TestCase):
    def test_freeze_summary_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            scorecard = root / "scorecard.json"
            benchmark = root / "benchmark.json"
            quality = root / "quality.json"
            out = root / "summary.json"

            scorecard.write_text(json.dumps({"baseline_id": "moat-baseline-test", "failure_distribution_stability_score": 90.0}), encoding="utf-8")
            benchmark.write_text(json.dumps({"total_cases_after": 9, "failure_type_drift": 0.03, "model_scale_drift": 0.04}), encoding="utf-8")
            quality.write_text(json.dumps({"gate_result": "PASS", "unique_failure_types": 6}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_baseline_freeze_v1",
                    "--moat-scorecard-baseline-summary",
                    str(scorecard),
                    "--failure-distribution-benchmark-summary",
                    str(benchmark),
                    "--failure-distribution-quality-gate-summary",
                    str(quality),
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
            self.assertIsInstance(payload.get("freeze_id"), str)

    def test_freeze_fails_on_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_failure_distribution_baseline_freeze_v1",
                    "--moat-scorecard-baseline-summary",
                    str(root / "missing1.json"),
                    "--failure-distribution-benchmark-summary",
                    str(root / "missing2.json"),
                    "--failure-distribution-quality-gate-summary",
                    str(root / "missing3.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
