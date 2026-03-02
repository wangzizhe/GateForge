import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatExecutionCadenceV1Tests(unittest.TestCase):
    def test_cadence_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "plan.json"
            depth = root / "depth.json"
            supply = root / "supply.json"
            campaign = root / "campaign.json"
            out = root / "summary.json"
            plan.write_text(json.dumps({"status": "PASS", "execution_focus_score": 80.0}), encoding="utf-8")
            depth.write_text(json.dumps({"status": "PASS", "mutation_depth_pressure_index": 28.0, "recommended_weekly_mutation_target": 10}), encoding="utf-8")
            supply.write_text(json.dumps({"status": "PASS", "growth_velocity_score": 82.0, "supply_pipeline_score": 79.0}), encoding="utf-8")
            campaign.write_text(json.dumps({"status": "PASS", "completion_ratio_pct": 76.0}), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_moat_execution_cadence_v1", "--moat-hard-evidence-plan-summary", str(plan), "--mutation-depth-pressure-board-summary", str(depth), "--real-model-supply-pipeline-summary", str(supply), "--mutation-campaign-tracker-summary", str(campaign), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn("execution_cadence_score", payload)

    def test_cadence_fail_on_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run([sys.executable, "-m", "gateforge.dataset_moat_execution_cadence_v1", "--moat-hard-evidence-plan-summary", str(root / "m1.json"), "--mutation-depth-pressure-board-summary", str(root / "m2.json"), "--real-model-supply-pipeline-summary", str(root / "m3.json"), "--mutation-campaign-tracker-summary", str(root / "m4.json"), "--out", str(out)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
