import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPromotionCandidateAdvisorTests(unittest.TestCase):
    def test_advisor_promote_on_stable_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "advisor.json"
            snapshot.write_text(json.dumps({"status": "PASS", "risks": []}), encoding="utf-8")
            history.write_text(
                json.dumps({"latest_final_status": "PASS", "fail_rate": 0.0, "needs_review_rate": 0.1}),
                encoding="utf-8",
            )
            trend.write_text(json.dumps({"status": "PASS", "trend": {"alerts": []}}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_candidate_advisor",
                    "--snapshot",
                    str(snapshot),
                    "--strategy-apply-history",
                    str(history),
                    "--strategy-apply-history-trend",
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
            self.assertEqual((payload.get("advice") or {}).get("decision"), "PROMOTE")

    def test_advisor_hold_on_needs_review_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "advisor.json"
            snapshot.write_text(json.dumps({"status": "NEEDS_REVIEW", "risks": ["x"]}), encoding="utf-8")
            history.write_text(
                json.dumps({"latest_final_status": "PASS", "fail_rate": 0.0, "needs_review_rate": 0.2}),
                encoding="utf-8",
            )
            trend.write_text(json.dumps({"status": "PASS", "trend": {"alerts": []}}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_candidate_advisor",
                    "--snapshot",
                    str(snapshot),
                    "--strategy-apply-history",
                    str(history),
                    "--strategy-apply-history-trend",
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
            self.assertEqual((payload.get("advice") or {}).get("decision"), "HOLD")

    def test_advisor_block_on_fail_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            history = root / "history.json"
            trend = root / "trend.json"
            out = root / "advisor.json"
            snapshot.write_text(json.dumps({"status": "FAIL", "risks": ["pipeline"]}), encoding="utf-8")
            history.write_text(
                json.dumps({"latest_final_status": "FAIL", "fail_rate": 0.5, "needs_review_rate": 0.2}),
                encoding="utf-8",
            )
            trend.write_text(json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["x"]}}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_candidate_advisor",
                    "--snapshot",
                    str(snapshot),
                    "--strategy-apply-history",
                    str(history),
                    "--strategy-apply-history-trend",
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
            self.assertEqual((payload.get("advice") or {}).get("decision"), "BLOCK")


if __name__ == "__main__":
    unittest.main()
