import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetScaleTargetGapV1Tests(unittest.TestCase):
    def test_target_gap_reports_progress(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            batch = root / "batch.json"
            history = root / "history.json"
            out = root / "summary.json"

            batch.write_text(
                json.dumps(
                    {
                        "canonical_total_models": 600,
                        "reproducible_mutations": 2000,
                        "hard_moat_hardness_score": 76.0,
                        "hard_moat_gates_status": "PASS",
                    }
                ),
                encoding="utf-8",
            )
            history.write_text(
                json.dumps(
                    {
                        "delta_canonical_total_models": 20,
                        "delta_reproducible_mutations": 120,
                        "avg_canonical_net_growth_models": 10.0,
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_target_gap_v1",
                    "--scale-batch-summary",
                    str(batch),
                    "--scale-batch-history-summary",
                    str(history),
                    "--target-model-pool-size",
                    "800",
                    "--target-reproducible-mutations",
                    "3000",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(float(payload.get("overall_progress_pct", 0.0)), 0.0)
            self.assertGreaterEqual(int(payload.get("required_weekly_new_models", 0)), 0)

    def test_target_gap_fail_when_missing_batch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_target_gap_v1",
                    "--scale-batch-summary",
                    str(root / "missing.json"),
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
