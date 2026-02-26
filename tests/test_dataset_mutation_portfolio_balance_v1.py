import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationPortfolioBalanceV1Tests(unittest.TestCase):
    def test_portfolio_needs_review_when_large_ratio_low(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            saturation = root / "saturation.json"
            chain = root / "chain.json"
            out = root / "summary.json"

            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m1", "target_scale": "small", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "m2", "target_scale": "small", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "m3", "target_scale": "medium", "expected_failure_type": "model_check_error"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            saturation.write_text(
                json.dumps({"target_failure_types": ["simulate_error", "model_check_error", "semantic_regression"], "total_gap_actions": 3}),
                encoding="utf-8",
            )
            chain.write_text(json.dumps({"chain_health_score": 80.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_portfolio_balance_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--failure-corpus-saturation-summary",
                    str(saturation),
                    "--evidence-chain-summary",
                    str(chain),
                    "--min-large-mutation-ratio-pct",
                    "25",
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
            self.assertIn("large_mutation_ratio_low", summary.get("alerts", []))

    def test_portfolio_pass_when_balanced(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            saturation = root / "saturation.json"
            out = root / "summary.json"

            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m1", "target_scale": "large", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "m2", "target_scale": "large", "expected_failure_type": "model_check_error"},
                            {"mutation_id": "m3", "target_scale": "medium", "expected_failure_type": "semantic_regression"},
                            {"mutation_id": "m4", "target_scale": "small", "expected_failure_type": "numerical_instability"},
                            {"mutation_id": "m5", "target_scale": "medium", "expected_failure_type": "constraint_violation"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            saturation.write_text(
                json.dumps(
                    {"target_failure_types": ["simulate_error", "model_check_error", "semantic_regression", "numerical_instability", "constraint_violation"], "total_gap_actions": 0}
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_portfolio_balance_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--failure-corpus-saturation-summary",
                    str(saturation),
                    "--min-large-mutation-ratio-pct",
                    "20",
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

    def test_portfolio_fails_when_required_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_portfolio_balance_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--failure-corpus-saturation-summary",
                    str(root / "missing_saturation.json"),
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
