import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePolicyPatchHistoryTests(unittest.TestCase):
    def _write_apply(
        self,
        path: Path,
        proposal_id: str,
        final_status: str,
        applied: bool,
        decision: str | None,
        decisions: list[str] | None = None,
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": proposal_id,
                    "final_status": final_status,
                    "apply_action": "applied" if applied else "hold",
                    "approval_decision": decision,
                    "approval_decisions": decisions,
                    "applied": applied,
                    "reasons": [] if final_status == "PASS" else ["x"],
                    "target_policy_path": "tmp/policy.json",
                    "proposal_path": str(path.with_name(f"{proposal_id}.proposal.json")),
                }
            ),
            encoding="utf-8",
        )
        Path(path.with_name(f"{proposal_id}.proposal.json")).write_text(
            json.dumps(
                {
                    "policy_after": {
                        "require_min_pairwise_net_margin": 3 if final_status == "PASS" else None,
                    }
                }
            ),
            encoding="utf-8",
        )

    def test_builds_history_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record1 = root / "apply1.json"
            record2 = root / "apply2.json"
            record3 = root / "apply3.json"
            ledger = root / "history.jsonl"
            out = root / "summary.json"

            self._write_apply(record1, "p1", "NEEDS_REVIEW", False, None)
            self._write_apply(record2, "p2", "FAIL", False, None, ["reject"])
            self._write_apply(record3, "p3", "PASS", True, "approve")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_history",
                    "--record",
                    str(record1),
                    "--record",
                    str(record2),
                    "--record",
                    str(record3),
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
            self.assertEqual(payload.get("ingested_count"), 3)
            self.assertEqual(payload.get("total_records"), 3)
            self.assertEqual(payload.get("latest_status"), "PASS")
            self.assertEqual((payload.get("status_counts") or {}).get("PASS"), 1)
            self.assertEqual((payload.get("status_counts") or {}).get("NEEDS_REVIEW"), 1)
            self.assertEqual((payload.get("status_counts") or {}).get("FAIL"), 1)
            self.assertEqual(payload.get("applied_count"), 1)
            self.assertEqual(payload.get("reject_count"), 1)
            self.assertEqual(payload.get("pairwise_threshold_enabled_count"), 1)
            self.assertEqual(payload.get("latest_pairwise_threshold"), 3)
            self.assertTrue(ledger.exists())
            self.assertEqual(len(ledger.read_text(encoding="utf-8").strip().splitlines()), 3)

    def test_reads_existing_ledger_without_new_records(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "history.jsonl"
            out = root / "summary.json"
            ledger.write_text(
                "\n".join(
                    [
                        json.dumps({"final_status": "FAIL", "applied": False, "approval_decision": "reject"}),
                        json.dumps(
                            {
                                "final_status": "PASS",
                                "applied": True,
                                "approval_decision": "approve",
                                "pairwise_threshold": 2,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_history",
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
            self.assertEqual(payload.get("ingested_count"), 0)
            self.assertEqual(payload.get("total_records"), 2)
            self.assertEqual(payload.get("latest_status"), "PASS")
            self.assertEqual(payload.get("pairwise_threshold_enabled_count"), 1)
            self.assertEqual(payload.get("latest_pairwise_threshold"), 2)


if __name__ == "__main__":
    unittest.main()
