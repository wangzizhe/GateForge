import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernanceReplaySnapshotTests(unittest.TestCase):
    def test_snapshot_builds_from_replay_assets(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "history.jsonl"
            history = root / "history_summary.json"
            risk = root / "risk.json"
            compare = root / "compare.json"
            out = root / "snapshot.json"

            ledger.write_text(
                json.dumps(
                    {
                        "recorded_at_utc": "2026-02-23T10:00:00Z",
                        "decision": "NEEDS_REVIEW",
                        "mismatch_count": 2,
                        "mismatches": [{"code": "apply_policy_hash_mismatch"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            history.write_text(
                json.dumps(
                    {
                        "total_rows": 3,
                        "mismatch_total": 4,
                        "latest_decision": "NEEDS_REVIEW",
                        "alerts": ["mismatch_volume_high"],
                    }
                ),
                encoding="utf-8",
            )
            risk.write_text(json.dumps({"risk": {"score": 70, "level": "high"}}), encoding="utf-8")
            compare.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "best_profile": "default",
                        "profile_results": [
                            {"profile": "default", "final_status": "NEEDS_REVIEW"},
                            {"profile": "industrial_strict", "final_status": "FAIL"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay_snapshot",
                    "--replay-ledger",
                    str(ledger),
                    "--replay-history-summary",
                    str(history),
                    "--replay-risk-summary",
                    str(risk),
                    "--replay-compare-summary",
                    str(compare),
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
            self.assertIn("replay_risk_level_high", payload.get("risks", []))
            self.assertIn("replay_compare_contains_fail_profile", payload.get("risks", []))


if __name__ == "__main__":
    unittest.main()
