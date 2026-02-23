import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernanceReplayHistoryTests(unittest.TestCase):
    def test_history_summary_alerts_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            rows = [
                {
                    "recorded_at_utc": "2026-02-20T10:00:00Z",
                    "decision": "PASS",
                    "mismatches": [],
                },
                {
                    "recorded_at_utc": "2026-02-20T10:05:00Z",
                    "decision": "NEEDS_REVIEW",
                    "mismatches": [{"code": "apply_policy_hash_mismatch"}],
                },
                {
                    "recorded_at_utc": "2026-02-20T10:10:00Z",
                    "decision": "FAIL",
                    "mismatches": [{"code": "apply_policy_hash_mismatch"}, {"code": "apply_reasons_mismatch"}],
                },
            ]
            ledger.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay_history",
                    "--ledger",
                    str(ledger),
                    "--last-n",
                    "3",
                    "--mismatch-threshold",
                    "2",
                    "--non-pass-streak-threshold",
                    "2",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_records"), 3)
            self.assertEqual(payload.get("window_size"), 3)
            self.assertEqual(payload.get("latest_decision"), "FAIL")
            self.assertEqual(payload.get("decision_counts", {}).get("PASS"), 1)
            self.assertEqual(payload.get("decision_counts", {}).get("NEEDS_REVIEW"), 1)
            self.assertEqual(payload.get("decision_counts", {}).get("FAIL"), 1)
            self.assertEqual(payload.get("mismatch_total"), 3)
            self.assertIn("mismatch_volume_high", payload.get("alerts", []))
            self.assertIn("replay_non_pass_streak_detected", payload.get("alerts", []))

    def test_history_summary_handles_missing_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay_history",
                    "--ledger",
                    str(root / "missing.jsonl"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_records"), 0)
            self.assertEqual(payload.get("window_size"), 0)
            self.assertEqual(payload.get("alerts"), [])


if __name__ == "__main__":
    unittest.main()
