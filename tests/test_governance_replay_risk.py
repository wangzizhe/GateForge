import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernanceReplayRiskTests(unittest.TestCase):
    def test_risk_score_high_for_fail_streak_with_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "history.jsonl"
            out = root / "risk.json"
            rows = [
                {
                    "recorded_at_utc": "2026-02-23T10:00:00Z",
                    "decision": "NEEDS_REVIEW",
                    "mismatches": [{"code": "apply_policy_hash_mismatch"}],
                },
                {
                    "recorded_at_utc": "2026-02-23T10:05:00Z",
                    "decision": "FAIL",
                    "mismatches": [
                        {"code": "apply_policy_hash_mismatch"},
                        {"code": "apply_reasons_mismatch"},
                    ],
                },
            ]
            ledger.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay_risk",
                    "--ledger",
                    str(ledger),
                    "--last-n",
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
            self.assertEqual(payload.get("risk", {}).get("level"), "high")
            self.assertGreaterEqual(int(payload.get("risk", {}).get("score", 0)), 60)

    def test_risk_score_low_for_clean_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "history.jsonl"
            out = root / "risk.json"
            ledger.write_text(
                json.dumps(
                    {
                        "recorded_at_utc": "2026-02-23T10:00:00Z",
                        "decision": "PASS",
                        "mismatches": [],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay_risk",
                    "--ledger",
                    str(ledger),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("risk", {}).get("level"), "low")


if __name__ == "__main__":
    unittest.main()
