import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetBlindSpotBacklogTests(unittest.TestCase):
    def test_backlog_needs_review_with_blind_spots(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taxonomy = root / "taxonomy.json"
            distribution = root / "distribution.json"
            registry = root / "registry.json"
            snapshot = root / "snapshot.json"
            out = root / "summary.json"
            taxonomy.write_text(
                json.dumps(
                    {
                        "missing_failure_types": ["stability_regression"],
                        "missing_model_scales": ["large"],
                        "missing_stages": ["compile"],
                    }
                ),
                encoding="utf-8",
            )
            distribution.write_text(
                json.dumps(
                    {
                        "distribution_drift_score": 0.4,
                        "false_positive_rate_after": 0.11,
                        "regression_rate_after": 0.2,
                    }
                ),
                encoding="utf-8",
            )
            registry.write_text(json.dumps({"missing_model_scales": ["large"]}), encoding="utf-8")
            snapshot.write_text(
                json.dumps({"risks": ["dataset_failure_distribution_benchmark_needs_review"]}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_blind_spot_backlog",
                    "--failure-taxonomy-coverage",
                    str(taxonomy),
                    "--failure-distribution-benchmark",
                    str(distribution),
                    "--failure-corpus-registry-summary",
                    str(registry),
                    "--snapshot-summary",
                    str(snapshot),
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
            self.assertGreater(int(payload.get("total_open_tasks", 0) or 0), 0)

    def test_backlog_fail_with_no_sources(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_blind_spot_backlog",
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
