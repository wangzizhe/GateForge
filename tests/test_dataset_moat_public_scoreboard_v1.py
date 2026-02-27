import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatPublicScoreboardV1Tests(unittest.TestCase):
    def test_scoreboard_pass_when_components_strong(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            release = root / "release.json"
            chain = root / "chain.json"
            roadmap = root / "roadmap.json"
            campaign = root / "campaign.json"
            expansion = root / "expansion.json"
            out = root / "summary.json"

            release.write_text(json.dumps({"status": "PASS", "public_release_score": 90.0}), encoding="utf-8")
            chain.write_text(json.dumps({"status": "PASS", "chain_health_score": 85.0}), encoding="utf-8")
            roadmap.write_text(json.dumps({"status": "PASS", "roadmap_health_score": 84.0}), encoding="utf-8")
            campaign.write_text(json.dumps({"status": "PASS", "completion_ratio_pct": 92.0}), encoding="utf-8")
            expansion.write_text(json.dumps({"status": "PASS", "expansion_readiness_score": 88.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_public_scoreboard_v1",
                    "--anchor-public-release-v1-summary",
                    str(release),
                    "--evidence-chain-summary",
                    str(chain),
                    "--modelica-moat-roadmap-v1-summary",
                    str(roadmap),
                    "--mutation-campaign-tracker-v1-summary",
                    str(campaign),
                    "--modelica-library-expansion-plan-v1-summary",
                    str(expansion),
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
            self.assertIn("real_model_supply_health_score", summary.get("score_breakdown", {}))
            self.assertIn("mutation_recipe_execution_coverage_pct", summary.get("score_breakdown", {}))
            self.assertIn("release_candidate_score", summary.get("score_breakdown", {}))

    def test_scoreboard_needs_review_when_scores_are_low(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            release = root / "release.json"
            chain = root / "chain.json"
            roadmap = root / "roadmap.json"
            campaign = root / "campaign.json"
            expansion = root / "expansion.json"
            out = root / "summary.json"

            release.write_text(json.dumps({"status": "NEEDS_REVIEW", "public_release_score": 68.0}), encoding="utf-8")
            chain.write_text(json.dumps({"status": "NEEDS_REVIEW", "chain_health_score": 62.0}), encoding="utf-8")
            roadmap.write_text(json.dumps({"status": "NEEDS_REVIEW", "roadmap_health_score": 60.0}), encoding="utf-8")
            campaign.write_text(json.dumps({"status": "NEEDS_REVIEW", "completion_ratio_pct": 50.0}), encoding="utf-8")
            expansion.write_text(json.dumps({"status": "NEEDS_REVIEW", "expansion_readiness_score": 64.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_public_scoreboard_v1",
                    "--anchor-public-release-v1-summary",
                    str(release),
                    "--evidence-chain-summary",
                    str(chain),
                    "--modelica-moat-roadmap-v1-summary",
                    str(roadmap),
                    "--mutation-campaign-tracker-v1-summary",
                    str(campaign),
                    "--modelica-library-expansion-plan-v1-summary",
                    str(expansion),
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
            self.assertIn("moat_public_score_below_target", summary.get("alerts", []))

    def test_scoreboard_fails_when_required_input_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_public_scoreboard_v1",
                    "--anchor-public-release-v1-summary",
                    str(root / "missing_release.json"),
                    "--evidence-chain-summary",
                    str(root / "missing_chain.json"),
                    "--modelica-moat-roadmap-v1-summary",
                    str(root / "missing_roadmap.json"),
                    "--mutation-campaign-tracker-v1-summary",
                    str(root / "missing_campaign.json"),
                    "--modelica-library-expansion-plan-v1-summary",
                    str(root / "missing_expansion.json"),
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
