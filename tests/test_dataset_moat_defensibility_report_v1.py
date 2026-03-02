import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatDefensibilityReportV1Tests(unittest.TestCase):
    def test_report_needs_review_when_signals_weak(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rep = root / "rep.json"
            uniq = root / "uniq.json"
            hist = root / "hist.json"
            tr = root / "tr.json"
            plan = root / "plan.json"
            out = root / "summary.json"

            rep.write_text(json.dumps({"representativeness_score": 65.0}), encoding="utf-8")
            uniq.write_text(json.dumps({"asset_uniqueness_index": 75.0}), encoding="utf-8")
            hist.write_text(json.dumps({"avg_pressure_index": 45.0}), encoding="utf-8")
            tr.write_text(json.dumps({"trend": {"delta_avg_stability_score": -1.0, "delta_avg_distribution_drift_score": 0.04}}), encoding="utf-8")
            plan.write_text(json.dumps({"execution_focus_score": 58.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_defensibility_report_v1",
                    "--modelica-representativeness-gate-summary",
                    str(rep),
                    "--modelica-asset-uniqueness-index-summary",
                    str(uniq),
                    "--mutation-depth-pressure-history-summary",
                    str(hist),
                    "--failure-distribution-stability-history-trend-summary",
                    str(tr),
                    "--moat-hard-evidence-plan-summary",
                    str(plan),
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

    def test_report_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_defensibility_report_v1",
                    "--modelica-representativeness-gate-summary",
                    str(root / "missing1.json"),
                    "--modelica-asset-uniqueness-index-summary",
                    str(root / "missing2.json"),
                    "--mutation-depth-pressure-history-summary",
                    str(root / "missing3.json"),
                    "--failure-distribution-stability-history-trend-summary",
                    str(root / "missing4.json"),
                    "--moat-hard-evidence-plan-summary",
                    str(root / "missing5.json"),
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
