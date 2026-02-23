import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernanceReplaySnapshotTrendTests(unittest.TestCase):
    def test_trend_contains_transition_and_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous = root / "previous.json"
            current = root / "current.json"
            out = root / "trend.json"
            previous.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "risks": ["replay_mismatch_volume_high"],
                        "kpis": {
                            "latest_mismatch_count": 0,
                            "history_mismatch_total": 1,
                            "risk_score": 10,
                            "compare_profile_count": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            current.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "risks": ["replay_non_pass_streak_detected"],
                        "kpis": {
                            "latest_mismatch_count": 2,
                            "history_mismatch_total": 4,
                            "risk_score": 45,
                            "compare_profile_count": 2,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay_snapshot_trend",
                    "--summary",
                    str(current),
                    "--previous-summary",
                    str(previous),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            trend = payload.get("trend", {})
            self.assertEqual(trend.get("status_transition"), "PASS->NEEDS_REVIEW")
            self.assertIn("replay_non_pass_streak_detected", trend.get("new_risks", []))
            self.assertIn("replay_mismatch_volume_high", trend.get("resolved_risks", []))
            self.assertIn("risk_score_delta", trend.get("kpi_delta", {}))


if __name__ == "__main__":
    unittest.main()
