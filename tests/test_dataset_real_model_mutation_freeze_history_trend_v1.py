import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelMutationFreezeHistoryTrendV1Tests(unittest.TestCase):
    def test_freeze_history_trend_detects_worsening(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "summary.json"

            previous.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "latest_freeze_status": "PASS",
                        "avg_accepted_models": 120.0,
                        "avg_generated_mutations": 1400.0,
                        "avg_reproducible_mutations": 1380.0,
                        "avg_canonical_net_growth_models": 8.0,
                        "avg_validation_type_match_rate_pct": 74.0,
                        "needs_review_rate": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "latest_freeze_status": "NEEDS_REVIEW",
                        "avg_accepted_models": 110.0,
                        "avg_generated_mutations": 1200.0,
                        "avg_reproducible_mutations": 1180.0,
                        "avg_canonical_net_growth_models": 5.0,
                        "avg_validation_type_match_rate_pct": 70.0,
                        "needs_review_rate": 0.5,
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_freeze_history_trend_v1",
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
            self.assertIn("avg_generated_mutations_decreasing", payload.get("alerts") or [])

    def test_freeze_history_trend_fail_on_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_mutation_freeze_history_trend_v1",
                    "--previous",
                    str(root / "missing_previous.json"),
                    "--current",
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
