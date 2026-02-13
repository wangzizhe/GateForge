import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ReviewTests(unittest.TestCase):
    def _write_source(
        self,
        path: Path,
        status: str = "NEEDS_REVIEW",
        review_policy: dict | None = None,
        proposal_author: str | None = None,
        risk_level: str = "low",
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": "proposal-review-001",
                    "status": status,
                    "policy_decision": status,
                    "risk_level": risk_level,
                    "policy_reasons": ["change_plan_confidence_below_auto_apply"] if status == "NEEDS_REVIEW" else [],
                    "required_human_checks": ["check-a", "check-b"],
                    "review_resolution_policy": review_policy or {},
                    "proposal_author": proposal_author,
                }
            ),
            encoding="utf-8",
        )

    def _write_review(
        self,
        path: Path,
        *,
        decision: str,
        all_done: bool = True,
        proposal_id: str = "proposal-review-001",
        reviewer: str = "human.reviewer",
        second_reviewer: str | None = None,
        second_decision: str | None = None,
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "review_id": "review-001",
                    "proposal_id": proposal_id,
                    "reviewer": reviewer,
                    "decision": decision,
                    "rationale": "manual decision",
                    "all_required_checks_completed": all_done,
                    "confirmed_checks": ["check-a", "check-b"],
                    "second_reviewer": second_reviewer,
                    "second_decision": second_decision,
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

    def test_resolve_fails_when_reviewer_matches_author(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            review = root / "review.json"
            out = root / "final.json"
            self._write_source(
                source,
                review_policy={"require_distinct_reviewer_from_source_author": True},
                proposal_author="human.reviewer",
            )
            self._write_review(review, decision="approve", reviewer="human.reviewer")
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
            self.assertIn("reviewer_matches_source_author", payload["final_reasons"])

    def test_resolve_fails_when_dual_review_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            review = root / "review.json"
            out = root / "final.json"
            self._write_source(
                source,
                review_policy={"require_dual_review_risk_levels": ["high"]},
                risk_level="high",
            )
            self._write_review(review, decision="approve")
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
            self.assertIn("dual_review_missing_second_reviewer", payload["final_reasons"])

    def test_resolve_passes_when_dual_review_approved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            review = root / "review.json"
            out = root / "final.json"
            self._write_source(
                source,
                review_policy={"require_dual_review_risk_levels": ["high"]},
                risk_level="high",
            )
            self._write_review(
                review,
                decision="approve",
                second_reviewer="human.reviewer.2",
                second_decision="approve",
            )
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


if __name__ == "__main__":
    unittest.main()
