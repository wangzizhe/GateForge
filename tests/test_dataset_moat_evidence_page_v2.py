import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatEvidencePageV2Tests(unittest.TestCase):
    def test_evidence_page_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            anchor = root / "anchor.json"
            growth = root / "growth.json"
            supply = root / "supply.json"
            matrix = root / "matrix.json"
            history = root / "history.json"
            trend = root / "trend.json"
            moat_snapshot = root / "moat_snapshot.json"
            out = root / "summary.json"
            anchor.write_text(json.dumps({"status": "PASS", "anchor_brief_score": 82.0}), encoding="utf-8")
            growth.write_text(json.dumps({"status": "PASS", "growth_velocity_score": 81.0}), encoding="utf-8")
            supply.write_text(json.dumps({"status": "PASS", "supply_pipeline_score": 84.0, "new_models_30d": 2, "large_model_candidates_30d": 1}), encoding="utf-8")
            matrix.write_text(json.dumps({"status": "PASS", "matrix_coverage_score": 83.0}), encoding="utf-8")
            history.write_text(json.dumps({"status": "PASS", "avg_stability_score": 80.0}), encoding="utf-8")
            trend.write_text(json.dumps({"status": "PASS", "trend": {"status_transition": "PASS->PASS"}}), encoding="utf-8")
            moat_snapshot.write_text(
                json.dumps({"metrics": {"target_gap_pressure_index": 76.5, "model_asset_target_gap_score": 20.0}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_evidence_page_v2",
                    "--moat-anchor-brief-summary",
                    str(anchor),
                    "--real-model-growth-trend-summary",
                    str(growth),
                    "--real-model-supply-pipeline-summary",
                    str(supply),
                    "--mutation-coverage-matrix-summary",
                    str(matrix),
                    "--failure-distribution-stability-history-summary",
                    str(history),
                    "--failure-distribution-stability-history-trend-summary",
                    str(trend),
                    "--moat-trend-snapshot-summary",
                    str(moat_snapshot),
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
            self.assertTrue(bool(payload.get("publishable")))
            self.assertIsInstance(payload.get("target_gap_pressure_index"), (int, float))
            self.assertIsInstance(payload.get("model_asset_target_gap_score"), (int, float))


if __name__ == "__main__":
    unittest.main()
