import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatHardEvidencePlanV1Tests(unittest.TestCase):
    def test_plan_needs_review_with_risks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rep = root / "rep.json"
            dep = root / "dep.json"
            st = root / "st.json"
            wk = root / "wk.json"
            out = root / "summary.json"

            rep.write_text(json.dumps({"status": "NEEDS_REVIEW", "representativeness_score": 62.0}), encoding="utf-8")
            dep.write_text(json.dumps({"status": "NEEDS_REVIEW", "mutation_depth_pressure_index": 48.0}), encoding="utf-8")
            st.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"delta_avg_stability_score": -1.0, "delta_avg_distribution_drift_score": 0.03}}),
                encoding="utf-8",
            )
            wk.write_text(json.dumps({"status": "NEEDS_REVIEW"}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_hard_evidence_plan_v1",
                    "--modelica-representativeness-gate-summary",
                    str(rep),
                    "--mutation-depth-pressure-board-summary",
                    str(dep),
                    "--failure-distribution-stability-history-trend-summary",
                    str(st),
                    "--moat-weekly-summary",
                    str(wk),
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
            self.assertGreater(int(payload.get("planned_actions_count", 0)), 0)

    def test_plan_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_hard_evidence_plan_v1",
                    "--modelica-representativeness-gate-summary",
                    str(root / "missing1.json"),
                    "--mutation-depth-pressure-board-summary",
                    str(root / "missing2.json"),
                    "--failure-distribution-stability-history-trend-summary",
                    str(root / "missing3.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
