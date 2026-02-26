import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelScaleLadderTests(unittest.TestCase):
    def test_pass_when_medium_and_large_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            coverage = root / "coverage.json"
            benchmark = root / "benchmark.json"
            out = root / "summary.json"
            coverage.write_text(
                json.dumps({"model_scale_counts": {"small": 5, "medium": 3, "large": 2}}),
                encoding="utf-8",
            )
            benchmark.write_text(
                json.dumps({"distribution": {"model_scale_after": {"small": 4, "medium": 2, "large": 1}}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_scale_ladder",
                    "--failure-taxonomy-coverage",
                    str(coverage),
                    "--failure-distribution-benchmark",
                    str(benchmark),
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
            self.assertTrue(payload.get("medium_ready"))
            self.assertTrue(payload.get("large_ready"))

    def test_needs_review_when_large_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            coverage = root / "coverage.json"
            benchmark = root / "benchmark.json"
            out = root / "summary.json"
            coverage.write_text(
                json.dumps({"model_scale_counts": {"small": 5, "medium": 2, "large": 1}}),
                encoding="utf-8",
            )
            benchmark.write_text(
                json.dumps({"distribution": {"model_scale_after": {"small": 5, "medium": 1, "large": 0}}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_scale_ladder",
                    "--failure-taxonomy-coverage",
                    str(coverage),
                    "--failure-distribution-benchmark",
                    str(benchmark),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertIn("large_scale_readiness_insufficient", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
