import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelAssetTargetGapV1Tests(unittest.TestCase):
    def test_target_gap_pass_when_targets_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            portfolio = root / "portfolio.json"
            momentum = root / "momentum.json"
            coverage = root / "coverage.json"
            stability = root / "stability.json"
            out = root / "summary.json"
            portfolio.write_text(json.dumps({"total_real_models": 14, "large_models": 5}), encoding="utf-8")
            momentum.write_text(
                json.dumps({"status": "PASS", "momentum_score": 88.0, "delta_total_real_models": 3, "delta_large_models": 1}),
                encoding="utf-8",
            )
            coverage.write_text(json.dumps({"coverage_depth_score": 90.0}), encoding="utf-8")
            stability.write_text(json.dumps({"stability_score": 84.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_asset_target_gap_v1",
                    "--real-model-intake-portfolio-summary",
                    str(portfolio),
                    "--model-asset-momentum-summary",
                    str(momentum),
                    "--mutation-coverage-depth-summary",
                    str(coverage),
                    "--failure-distribution-stability-summary",
                    str(stability),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(float(summary.get("target_gap_score", 1.0)), 0.0)

    def test_target_gap_needs_review_with_single_gap(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            portfolio = root / "portfolio.json"
            momentum = root / "momentum.json"
            coverage = root / "coverage.json"
            stability = root / "stability.json"
            out = root / "summary.json"
            portfolio.write_text(json.dumps({"total_real_models": 12, "large_models": 4}), encoding="utf-8")
            momentum.write_text(
                json.dumps({"status": "PASS", "momentum_score": 84.0, "delta_total_real_models": 2, "delta_large_models": 1}),
                encoding="utf-8",
            )
            coverage.write_text(json.dumps({"coverage_depth_score": 80.0}), encoding="utf-8")
            stability.write_text(json.dumps({"stability_score": 82.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_asset_target_gap_v1",
                    "--real-model-intake-portfolio-summary",
                    str(portfolio),
                    "--model-asset-momentum-summary",
                    str(momentum),
                    "--mutation-coverage-depth-summary",
                    str(coverage),
                    "--failure-distribution-stability-summary",
                    str(stability),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertGreater(float(summary.get("target_gap_score", 0.0)), 0.0)

    def test_target_gap_fail_when_critical_gaps_high(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            portfolio = root / "portfolio.json"
            momentum = root / "momentum.json"
            coverage = root / "coverage.json"
            stability = root / "stability.json"
            out = root / "summary.json"
            portfolio.write_text(json.dumps({"total_real_models": 4, "large_models": 0}), encoding="utf-8")
            momentum.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "momentum_score": 60.0, "delta_total_real_models": 0, "delta_large_models": 0}),
                encoding="utf-8",
            )
            coverage.write_text(json.dumps({"coverage_depth_score": 70.0}), encoding="utf-8")
            stability.write_text(json.dumps({"stability_score": 65.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_model_asset_target_gap_v1",
                    "--real-model-intake-portfolio-summary",
                    str(portfolio),
                    "--model-asset-momentum-summary",
                    str(momentum),
                    "--mutation-coverage-depth-summary",
                    str(coverage),
                    "--failure-distribution-stability-summary",
                    str(stability),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
