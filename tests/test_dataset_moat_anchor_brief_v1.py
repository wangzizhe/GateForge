import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatAnchorBriefV1Tests(unittest.TestCase):
    def test_anchor_brief_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            moat = root / "moat.json"
            portfolio = root / "portfolio.json"
            coverage = root / "coverage.json"
            stability = root / "stability.json"
            out = root / "summary.json"
            moat.write_text(json.dumps({"status": "PASS", "metrics": {"moat_score": 84.0, "execution_readiness_index": 82.0}}), encoding="utf-8")
            portfolio.write_text(json.dumps({"status": "PASS", "portfolio_strength_score": 83.0, "total_real_models": 5, "large_models": 2}), encoding="utf-8")
            coverage.write_text(json.dumps({"status": "PASS", "coverage_depth_score": 89.0, "high_risk_gaps_count": 0}), encoding="utf-8")
            stability.write_text(json.dumps({"status": "PASS", "stability_score": 81.0, "rare_failure_replay_rate": 1.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_anchor_brief_v1",
                    "--moat-trend-snapshot-summary",
                    str(moat),
                    "--real-model-intake-portfolio-summary",
                    str(portfolio),
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
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertIsInstance(payload.get("anchor_brief_score"), float)


if __name__ == "__main__":
    unittest.main()
