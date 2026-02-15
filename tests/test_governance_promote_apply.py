import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePromoteApplyTests(unittest.TestCase):
    def _write_compare_summary(
        self,
        path: Path,
        *,
        status: str,
        best_profile: str = "default",
        best_decision: str = "PASS",
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "status": status,
                    "best_profile": best_profile,
                    "best_decision": best_decision,
                    "recommended_profile": "default",
                    "best_total_score": 10,
                    "best_reason": "highest_total_score",
                    "top_score_margin": 3,
                    "min_top_score_margin": 1,
                }
            ),
            encoding="utf-8",
        )

    def test_apply_pass_promotes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            audit = root / "audit.jsonl"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--out",
                    str(out),
                    "--audit",
                    str(audit),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("final_status"), "PASS")
            self.assertEqual(payload.get("apply_action"), "promote")
            rows = [json.loads(x) for x in audit.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("final_status"), "PASS")

    def test_apply_needs_review_requires_ticket(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="NEEDS_REVIEW", best_decision="NEEDS_REVIEW")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("final_status"), "FAIL")
            self.assertIn("needs_review_ticket_required", payload.get("reasons", []))

    def test_apply_needs_review_with_ticket_holds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="NEEDS_REVIEW", best_decision="NEEDS_REVIEW")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--review-ticket-id",
                    "REV-123",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("final_status"), "NEEDS_REVIEW")
            self.assertEqual(payload.get("apply_action"), "hold_for_review")
            self.assertEqual(payload.get("review_ticket_id"), "REV-123")

    def test_apply_fail_when_compare_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="FAIL", best_decision="FAIL")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("final_status"), "FAIL")
            self.assertIn("compare_status_fail", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
