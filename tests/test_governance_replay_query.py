import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernanceReplayQueryTests(unittest.TestCase):
    def test_query_filters_by_decision_and_mismatch_code(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "history.jsonl"
            summary = root / "summary.json"
            export = root / "rows.json"
            rows = [
                {
                    "recorded_at_utc": "2026-02-23T10:00:00Z",
                    "decision": "PASS",
                    "mismatches": [],
                },
                {
                    "recorded_at_utc": "2026-02-23T10:05:00Z",
                    "decision": "NEEDS_REVIEW",
                    "mismatches": [{"code": "apply_policy_hash_mismatch"}],
                },
                {
                    "recorded_at_utc": "2026-02-23T10:10:00Z",
                    "decision": "FAIL",
                    "mismatches": [{"code": "apply_reasons_mismatch"}],
                },
            ]
            ledger.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_replay_query",
                    "--ledger",
                    str(ledger),
                    "--decision",
                    "NEEDS_REVIEW",
                    "--mismatch-code",
                    "apply_policy_hash_mismatch",
                    "--out",
                    str(summary),
                    "--export-out",
                    str(export),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("total_rows"), 1)
            self.assertEqual(payload.get("decision_counts", {}).get("NEEDS_REVIEW"), 1)
            exported = json.loads(export.read_text(encoding="utf-8"))
            self.assertEqual(len(exported.get("rows", [])), 1)


if __name__ == "__main__":
    unittest.main()
