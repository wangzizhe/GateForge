import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMoatMilestoneEvidencePageV1Tests(unittest.TestCase):
    def test_evidence_page_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            moat = root / "moat.json"
            checkpoint = root / "checkpoint.json"
            trend = root / "trend.json"
            brief = root / "brief.json"
            align = root / "align.json"
            out = root / "summary.json"

            moat.write_text(json.dumps({"status": "PASS", "metrics": {"moat_score": 83.0}}), encoding="utf-8")
            checkpoint.write_text(json.dumps({"status": "PASS", "checkpoint_score": 85.0, "milestone_decision": "GO"}), encoding="utf-8")
            trend.write_text(json.dumps({"status": "PASS", "trend": {"status_transition": "PASS->PASS"}}), encoding="utf-8")
            brief.write_text(json.dumps({"milestone_status": "PASS", "milestone_decision": "GO"}), encoding="utf-8")
            align.write_text(json.dumps({"alignment_score": 82.0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_milestone_evidence_page_v1",
                    "--moat-trend-snapshot-summary",
                    str(moat),
                    "--milestone-checkpoint-summary",
                    str(checkpoint),
                    "--milestone-checkpoint-trend-summary",
                    str(trend),
                    "--milestone-public-brief-summary",
                    str(brief),
                    "--snapshot-moat-alignment-summary",
                    str(align),
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
            self.assertEqual(payload.get("publishable"), True)
            self.assertGreaterEqual(float(payload.get("evidence_page_score", 0.0)), 76.0)

    def test_evidence_page_fail_when_required_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_moat_milestone_evidence_page_v1",
                    "--moat-trend-snapshot-summary",
                    str(root / "missing_moat.json"),
                    "--milestone-checkpoint-summary",
                    str(root / "missing_checkpoint.json"),
                    "--milestone-public-brief-summary",
                    str(root / "missing_brief.json"),
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
