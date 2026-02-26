import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationCampaignTrackerV1Tests(unittest.TestCase):
    def test_tracker_pass_when_campaign_execution_is_strong(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            portfolio = root / "portfolio.json"
            expansion = root / "expansion.json"
            chain = root / "chain.json"
            replay = root / "replay.json"
            out = root / "summary.json"

            manifest.write_text(
                json.dumps({"mutations": [{"mutation_id": f"m{i}"} for i in range(1, 13)]}),
                encoding="utf-8",
            )
            portfolio.write_text(json.dumps({"status": "PASS", "portfolio_balance_score": 82.0, "rebalance_actions": []}), encoding="utf-8")
            expansion.write_text(json.dumps({"weekly_new_models_target": 4}), encoding="utf-8")
            chain.write_text(json.dumps({"status": "PASS", "chain_health_score": 84.0}), encoding="utf-8")
            replay.write_text(json.dumps({"ingested_records": 10}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_campaign_tracker_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-portfolio-balance-summary",
                    str(portfolio),
                    "--modelica-library-expansion-plan-summary",
                    str(expansion),
                    "--evidence-chain-summary",
                    str(chain),
                    "--replay-observation-store-summary",
                    str(replay),
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

    def test_tracker_needs_review_when_completion_low(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            portfolio = root / "portfolio.json"
            expansion = root / "expansion.json"
            chain = root / "chain.json"
            replay = root / "replay.json"
            out = root / "summary.json"

            manifest.write_text(json.dumps({"mutations": [{"mutation_id": f"m{i}"} for i in range(1, 20)]}), encoding="utf-8")
            portfolio.write_text(json.dumps({"status": "NEEDS_REVIEW", "portfolio_balance_score": 65.0, "rebalance_actions": [{"id": "a1"}]}), encoding="utf-8")
            expansion.write_text(json.dumps({"weekly_new_models_target": 6}), encoding="utf-8")
            chain.write_text(json.dumps({"status": "NEEDS_REVIEW", "chain_health_score": 60.0}), encoding="utf-8")
            replay.write_text(json.dumps({"ingested_records": 2}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_campaign_tracker_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-portfolio-balance-summary",
                    str(portfolio),
                    "--modelica-library-expansion-plan-summary",
                    str(expansion),
                    "--evidence-chain-summary",
                    str(chain),
                    "--replay-observation-store-summary",
                    str(replay),
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
            self.assertIn("weekly_completion_ratio_low", summary.get("alerts", []))

    def test_tracker_fails_when_required_input_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_campaign_tracker_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--mutation-portfolio-balance-summary",
                    str(root / "missing_portfolio.json"),
                    "--modelica-library-expansion-plan-summary",
                    str(root / "missing_expansion.json"),
                    "--evidence-chain-summary",
                    str(root / "missing_chain.json"),
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
