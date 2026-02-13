import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ReviewLedgerTests(unittest.TestCase):
    def _write_source(self, path: Path, proposal_id: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": proposal_id,
                    "status": "NEEDS_REVIEW",
                    "policy_decision": "NEEDS_REVIEW",
                    "required_human_checks": ["check-a"],
                }
            ),
            encoding="utf-8",
        )

    def _write_review(self, path: Path, proposal_id: str, decision: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "review_id": f"review-{proposal_id}",
                    "proposal_id": proposal_id,
                    "reviewer": "human.reviewer",
                    "decision": decision,
                    "rationale": "decision",
                    "all_required_checks_completed": True,
                }
            ),
            encoding="utf-8",
        )

    def test_review_resolve_appends_ledger_and_updates_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "ledger.jsonl"
            ledger_summary = root / "ledger_summary.json"

            source1 = root / "source1.json"
            review1 = root / "review1.json"
            out1 = root / "final1.json"
            self._write_source(source1, "proposal-1")
            self._write_review(review1, "proposal-1", "approve")

            proc1 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.review_resolve",
                    "--summary",
                    str(source1),
                    "--review",
                    str(review1),
                    "--out",
                    str(out1),
                    "--ledger",
                    str(ledger),
                    "--ledger-summary-out",
                    str(ledger_summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc1.returncode, 0, msg=proc1.stderr or proc1.stdout)

            source2 = root / "source2.json"
            review2 = root / "review2.json"
            out2 = root / "final2.json"
            self._write_source(source2, "proposal-2")
            self._write_review(review2, "proposal-2", "reject")

            proc2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.review_resolve",
                    "--summary",
                    str(source2),
                    "--review",
                    str(review2),
                    "--out",
                    str(out2),
                    "--ledger",
                    str(ledger),
                    "--ledger-summary-out",
                    str(ledger_summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc2.returncode, 1)

            lines = ledger.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)

            payload = json.loads(ledger_summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_records"], 2)
            self.assertEqual(payload["status_counts"].get("PASS"), 1)
            self.assertEqual(payload["status_counts"].get("FAIL"), 1)

    def test_review_ledger_cli_summarizes_existing_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = root / "ledger.jsonl"
            ledger.write_text(
                "\n".join(
                    [
                        json.dumps({"final_status": "PASS", "reviewer": "r1", "final_reasons": []}),
                        json.dumps({"final_status": "FAIL", "reviewer": "r2", "final_reasons": ["human_rejected"]}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary_out = root / "summary.json"
            report_out = root / "summary.md"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.review_ledger",
                    "--ledger",
                    str(ledger),
                    "--summary-out",
                    str(summary_out),
                    "--report-out",
                    str(report_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(summary_out.read_text(encoding="utf-8"))
            self.assertEqual(summary["total_records"], 2)
            self.assertEqual(summary["status_counts"].get("PASS"), 1)
            self.assertEqual(summary["status_counts"].get("FAIL"), 1)
            self.assertTrue(report_out.exists())


if __name__ == "__main__":
    unittest.main()
