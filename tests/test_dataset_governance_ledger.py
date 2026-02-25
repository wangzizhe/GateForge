import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetGovernanceLedgerTests(unittest.TestCase):
    def _write_apply(
        self,
        path: Path,
        proposal_id: str,
        final_status: str,
        applied: bool,
        decisions: list[str],
        advisor_action: str,
    ) -> None:
        proposal_path = path.with_name(f"{proposal_id}.proposal.json")
        proposal_path.write_text(
            json.dumps({"advisor_suggested_action": advisor_action}),
            encoding="utf-8",
        )
        path.write_text(
            json.dumps(
                {
                    "proposal_id": proposal_id,
                    "final_status": final_status,
                    "apply_action": "applied" if applied else "hold",
                    "approval_decisions": decisions,
                    "applied": applied,
                    "target_policy_path": "tmp/policy.json",
                    "proposal_path": str(proposal_path),
                }
            ),
            encoding="utf-8",
        )

    def test_builds_ledger_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record1 = root / "apply1.json"
            record2 = root / "apply2.json"
            ledger = root / "ledger.jsonl"
            out = root / "summary.json"
            self._write_apply(record1, "p1", "PASS", True, ["approve"], "expand_mutation")
            self._write_apply(record2, "p2", "FAIL", False, ["reject"], "hold_release")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_governance_ledger",
                    "--record",
                    str(record1),
                    "--record",
                    str(record2),
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
            self.assertEqual(payload.get("total_records"), 2)
            self.assertEqual(payload.get("applied_count"), 1)
            self.assertEqual(payload.get("reject_count"), 1)
            self.assertEqual((payload.get("advisor_action_counts") or {}).get("expand_mutation"), 1)
            self.assertEqual((payload.get("advisor_action_counts") or {}).get("hold_release"), 1)


if __name__ == "__main__":
    unittest.main()

