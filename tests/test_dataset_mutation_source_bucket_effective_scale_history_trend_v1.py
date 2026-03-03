import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationSourceBucketEffectiveScaleHistoryTrendV1Tests(unittest.TestCase):
    def test_trend_needs_review_on_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "trend.json"
            previous.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "latest_source_bucket_count": 4,
                        "latest_effective_mutations": 100,
                        "latest_max_bucket_share_pct": 35.0,
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "latest_source_bucket_count": 2,
                        "latest_effective_mutations": 70,
                        "latest_max_bucket_share_pct": 65.0,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_source_bucket_effective_scale_history_trend_v1",
                    "--previous",
                    str(previous),
                    "--current",
                    str(current),
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


if __name__ == "__main__":
    unittest.main()
