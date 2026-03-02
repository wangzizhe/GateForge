import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatScorecardBaselineV1Tests(unittest.TestCase):
    def test_scorecard_builds_fixed_indicators(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            portfolio = root / "portfolio.json"
            matrix = root / "matrix.json"
            benchmark = root / "benchmark.json"
            compare = root / "compare.json"
            moat = root / "moat.json"
            out = root / "summary.json"

            portfolio.write_text(json.dumps({"total_real_models": 4}), encoding="utf-8")
            matrix.write_text(json.dumps({"matrix_cell_count": 12}), encoding="utf-8")
            benchmark.write_text(json.dumps({"failure_type_drift": 0.08, "model_scale_drift": 0.12}), encoding="utf-8")
            compare.write_text(json.dumps({"advantage_score": 10}), encoding="utf-8")
            moat.write_text(json.dumps({"moat_score": 74.2}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_scorecard_baseline_v1",
                    "--real-model-intake-portfolio-summary",
                    str(portfolio),
                    "--mutation-execution-matrix-summary",
                    str(matrix),
                    "--failure-distribution-benchmark-summary",
                    str(benchmark),
                    "--gateforge-vs-plain-ci-benchmark-summary",
                    str(compare),
                    "--moat-trend-snapshot-summary",
                    str(moat),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            indicators = payload.get("indicators") if isinstance(payload.get("indicators"), dict) else {}
            self.assertEqual(int(indicators.get("real_model_count", -1)), 4)
            self.assertEqual(int(indicators.get("reproducible_mutation_count", -1)), 12)
            self.assertIsInstance(indicators.get("failure_distribution_stability_score"), (int, float))
            self.assertIsInstance(payload.get("baseline_id"), str)

    def test_scorecard_fails_when_required_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_scorecard_baseline_v1",
                    "--real-model-intake-portfolio-summary",
                    str(root / "missing1.json"),
                    "--mutation-execution-matrix-summary",
                    str(root / "missing2.json"),
                    "--failure-distribution-benchmark-summary",
                    str(root / "missing3.json"),
                    "--gateforge-vs-plain-ci-benchmark-summary",
                    str(root / "missing4.json"),
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
