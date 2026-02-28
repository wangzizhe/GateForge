import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetRealModelGrowthTrendV1Tests(unittest.TestCase):
    def test_growth_trend_pass_when_improving(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "summary.json"
            previous.write_text(
                json.dumps({"total_real_models": 3, "large_models": 1, "active_domains_count": 2, "portfolio_strength_score": 70.0}),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps({"total_real_models": 5, "large_models": 2, "active_domains_count": 3, "portfolio_strength_score": 84.0}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_growth_trend_v1",
                    "--current-portfolio-summary",
                    str(current),
                    "--previous-portfolio-summary",
                    str(previous),
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
            self.assertGreater(payload.get("growth_velocity_score", 0), 60)

    def test_growth_trend_needs_review_when_declining(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "summary.json"
            previous.write_text(
                json.dumps({"total_real_models": 5, "large_models": 2, "active_domains_count": 3, "portfolio_strength_score": 84.0}),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps({"total_real_models": 4, "large_models": 1, "active_domains_count": 2, "portfolio_strength_score": 71.0}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_growth_trend_v1",
                    "--current-portfolio-summary",
                    str(current),
                    "--previous-portfolio-summary",
                    str(previous),
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
            self.assertIn("real_model_total_decreased", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
