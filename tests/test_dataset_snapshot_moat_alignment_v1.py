import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetSnapshotMoatAlignmentV1Tests(unittest.TestCase):
    def test_alignment_pass_when_signals_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            scoreboard = root / "scoreboard.json"
            campaign = root / "campaign.json"
            supply = root / "supply.json"
            release_candidate = root / "release_candidate.json"
            out = root / "summary.json"

            snapshot.write_text(json.dumps({"status": "PASS", "risks": []}), encoding="utf-8")
            trend.write_text(json.dumps({"status": "PASS", "trend": {"severity_score": 1}}), encoding="utf-8")
            scoreboard.write_text(json.dumps({"status": "PASS", "moat_public_score": 86.0}), encoding="utf-8")
            campaign.write_text(json.dumps({"status": "PASS", "completion_ratio_pct": 92.0}), encoding="utf-8")
            supply.write_text(json.dumps({"status": "PASS", "supply_health_score": 84.0}), encoding="utf-8")
            release_candidate.write_text(
                json.dumps({"status": "PASS", "release_candidate_score": 84.0, "candidate_decision": "GO"}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_snapshot_moat_alignment_v1",
                    "--governance-snapshot-summary",
                    str(snapshot),
                    "--governance-snapshot-trend-summary",
                    str(trend),
                    "--moat-public-scoreboard-summary",
                    str(scoreboard),
                    "--mutation-campaign-tracker-summary",
                    str(campaign),
                    "--real-model-supply-health-summary",
                    str(supply),
                    "--modelica-release-candidate-gate-summary",
                    str(release_candidate),
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
            self.assertIn("supply_status", summary.get("signals", {}))
            self.assertIn("release_candidate_status", summary.get("signals", {}))

    def test_alignment_needs_review_on_contradictions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            scoreboard = root / "scoreboard.json"
            campaign = root / "campaign.json"
            release_candidate = root / "release_candidate.json"
            out = root / "summary.json"

            snapshot.write_text(json.dumps({"status": "PASS", "risks": []}), encoding="utf-8")
            trend.write_text(json.dumps({"status": "NEEDS_REVIEW", "trend": {"severity_score": 7}}), encoding="utf-8")
            scoreboard.write_text(json.dumps({"status": "PASS", "moat_public_score": 88.0}), encoding="utf-8")
            campaign.write_text(json.dumps({"status": "NEEDS_REVIEW", "completion_ratio_pct": 55.0}), encoding="utf-8")
            release_candidate.write_text(
                json.dumps({"status": "PASS", "release_candidate_score": 86.0, "candidate_decision": "GO"}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_snapshot_moat_alignment_v1",
                    "--governance-snapshot-summary",
                    str(snapshot),
                    "--governance-snapshot-trend-summary",
                    str(trend),
                    "--moat-public-scoreboard-summary",
                    str(scoreboard),
                    "--mutation-campaign-tracker-summary",
                    str(campaign),
                    "--modelica-release-candidate-gate-summary",
                    str(release_candidate),
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
            self.assertGreaterEqual(int(summary.get("contradiction_count", 0)), 1)

    def test_alignment_fail_when_required_input_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_snapshot_moat_alignment_v1",
                    "--governance-snapshot-summary",
                    str(root / "missing_snapshot.json"),
                    "--governance-snapshot-trend-summary",
                    str(root / "missing_trend.json"),
                    "--moat-public-scoreboard-summary",
                    str(root / "missing_scoreboard.json"),
                    "--mutation-campaign-tracker-summary",
                    str(root / "missing_campaign.json"),
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
