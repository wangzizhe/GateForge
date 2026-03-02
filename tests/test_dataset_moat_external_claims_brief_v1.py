import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatExternalClaimsBriefV1Tests(unittest.TestCase):
    def test_claims_brief_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "report.json"
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "summary.json"
            report.write_text(json.dumps({"status": "PASS", "moat_defensibility_score": 85.0}), encoding="utf-8")
            history.write_text(json.dumps({"status": "PASS", "publish_ready_streak": 3, "avg_defensibility_score": 82.0}), encoding="utf-8")
            trend.write_text(json.dumps({"status": "PASS", "trend": {"delta_avg_defensibility_score": 1.2}}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_external_claims_brief_v1",
                    "--moat-defensibility-report-summary",
                    str(report),
                    "--moat-defensibility-history-summary",
                    str(history),
                    "--moat-defensibility-history-trend-summary",
                    str(trend),
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

    def test_claims_brief_fail_on_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_external_claims_brief_v1",
                    "--moat-defensibility-report-summary",
                    str(root / "missing1.json"),
                    "--moat-defensibility-history-summary",
                    str(root / "missing2.json"),
                    "--moat-defensibility-history-trend-summary",
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
