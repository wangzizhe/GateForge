import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ReviewTests(unittest.TestCase):
    def _write_source(self, path: Path, status: str = "NEEDS_REVIEW") -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": "proposal-review-001",
                    "status": status,
                    "policy_decision": status,
                    "required_human_checks": ["check-a", "check-b"],
                }
            ),
            encoding="utf-8",
        )

    def _write_review(self, path: Path, *, decision: str, all_done: bool = True, proposal_id: str = "proposal-review-001") -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "review_id": "review-001",
                    "proposal_id": proposal_id,
                    "reviewer": "human.reviewer",
                    "decision": decision,
                    "rationale": "manual decision",
                    "all_required_checks_completed": all_done,
                    "confirmed_checks": ["check-a", "check-b"],
                }
            ),
            encoding="utf-8",
        )

    def test_resolve_approve_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            review = root / "review.json"
            out = root / "final.json"
            self._write_source(source)
            self._write_review(review, decision="approve", all_done=True)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.review_resolve",
                    "--summary",
                    str(source),
                    "--review",
                    str(review),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["final_status"], "PASS")

    def test_resolve_reject_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            review = root / "review.json"
            out = root / "final.json"
            self._write_source(source)
            self._write_review(review, decision="reject")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.review_resolve",
                    "--summary",
                    str(source),
                    "--review",
                    str(review),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["final_status"], "FAIL")
            self.assertIn("human_rejected", payload["final_reasons"])

    def test_resolve_approve_without_checks_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            review = root / "review.json"
            out = root / "final.json"
            self._write_source(source)
            self._write_review(review, decision="approve", all_done=False)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.review_resolve",
                    "--summary",
                    str(source),
                    "--review",
                    str(review),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["final_status"], "FAIL")
            self.assertIn("required_human_checks_not_completed", payload["final_reasons"])

    def test_resolve_reject_on_proposal_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            review = root / "review.json"
            out = root / "final.json"
            self._write_source(source)
            self._write_review(review, decision="approve", proposal_id="proposal-other")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.review_resolve",
                    "--summary",
                    str(source),
                    "--review",
                    str(review),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("review_proposal_id_mismatch", payload["final_reasons"])


if __name__ == "__main__":
    unittest.main()
