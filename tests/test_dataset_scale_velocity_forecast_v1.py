import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetScaleVelocityForecastV1Tests(unittest.TestCase):
    def test_velocity_forecast_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gap = root / "gap.json"
            history = root / "history.json"
            out = root / "summary.json"
            gap.write_text(
                json.dumps({"gap_models": 60, "gap_reproducible_mutations": 1200, "target_horizon_weeks": 12}),
                encoding="utf-8",
            )
            history.write_text(
                json.dumps({"delta_canonical_total_models": 8, "delta_reproducible_mutations": 200}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_velocity_forecast_v1",
                    "--scale-target-gap-summary",
                    str(gap),
                    "--scale-history-summary",
                    str(history),
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
            self.assertGreaterEqual(int(payload.get("model_gap_weeks_to_close", 0)), 0)

    def test_velocity_forecast_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_velocity_forecast_v1",
                    "--scale-target-gap-summary",
                    str(root / "missing_gap.json"),
                    "--scale-history-summary",
                    str(root / "missing_history.json"),
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
