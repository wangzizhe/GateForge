import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelAssetMomentumV1Tests(unittest.TestCase):
    def test_momentum_scores_growth(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cur_portfolio = root / "cur_portfolio.json"
            prev_portfolio = root / "prev_portfolio.json"
            cur_coverage = root / "cur_coverage.json"
            prev_coverage = root / "prev_coverage.json"
            cur_stability = root / "cur_stability.json"
            prev_stability = root / "prev_stability.json"
            out = root / "summary.json"

            cur_portfolio.write_text(json.dumps({"total_real_models": 6, "large_models": 2}), encoding="utf-8")
            prev_portfolio.write_text(json.dumps({"total_real_models": 4, "large_models": 1}), encoding="utf-8")
            cur_coverage.write_text(json.dumps({"coverage_depth_score": 92.0}), encoding="utf-8")
            prev_coverage.write_text(json.dumps({"coverage_depth_score": 85.0}), encoding="utf-8")
            cur_stability.write_text(json.dumps({"stability_score": 84.0, "rare_failure_replay_rate": 1.0}), encoding="utf-8")
            prev_stability.write_text(json.dumps({"stability_score": 80.0, "rare_failure_replay_rate": 0.85}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_asset_momentum_v1",
                    "--current-intake-portfolio",
                    str(cur_portfolio),
                    "--previous-intake-portfolio",
                    str(prev_portfolio),
                    "--current-mutation-coverage-depth",
                    str(cur_coverage),
                    "--previous-mutation-coverage-depth",
                    str(prev_coverage),
                    "--current-failure-distribution-stability",
                    str(cur_stability),
                    "--previous-failure-distribution-stability",
                    str(prev_stability),
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
            self.assertGreaterEqual(float(payload.get("momentum_score", 0.0)), 72.0)
            self.assertEqual(int(payload.get("delta_total_real_models", 0)), 2)
            self.assertEqual(int(payload.get("delta_large_models", 0)), 1)


if __name__ == "__main__":
    unittest.main()
