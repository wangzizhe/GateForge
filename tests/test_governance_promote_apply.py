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
                    "decision_explanations": {
                        "selection_priority": [
                            "total_score",
                            "decision",
                            "exit_code",
                            "recommended_profile_tiebreak",
                        ],
                        "best_vs_others": [
                            {
                                "winner_profile": best_profile,
                                "challenger_profile": "industrial_strict",
                                "score_margin": 3,
                                "tie_on_total_score": False,
                                "winner_advantages": ["decision_component"],
                            }
                        ],
                    },
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
            self.assertEqual(payload.get("human_hints"), [])
            self.assertEqual(
                payload.get("ranking_selection_priority"),
                ["total_score", "decision", "exit_code", "recommended_profile_tiebreak"],
            )
            self.assertIsInstance(payload.get("ranking_best_vs_others"), list)
            rows = [json.loads(x) for x in audit.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("final_status"), "PASS")
            self.assertIsInstance(rows[0].get("ranking_best_vs_others"), list)

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
            self.assertTrue(payload.get("human_hints"))

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
            self.assertTrue(payload.get("human_hints"))

    def test_apply_fail_when_ranking_explanation_required_but_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            compare.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "best_profile": "default",
                        "best_decision": "PASS",
                        "recommended_profile": "default",
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-ranking-explanation",
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
            self.assertIn("ranking_explanation_required", payload.get("reasons", []))
            self.assertTrue(payload.get("human_hints"))

    def test_apply_fail_when_ranking_explanation_required_but_malformed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            compare.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "best_profile": "default",
                        "best_decision": "PASS",
                        "recommended_profile": "default",
                        "decision_explanations": {
                            "best_vs_others": [
                                {
                                    "winner_profile": "default",
                                    # malformed: challenger_profile missing
                                    "score_margin": "3",  # malformed: should be int
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-ranking-explanation",
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
            self.assertIn("ranking_explanation_required", payload.get("reasons", []))

    def test_apply_fail_when_required_top_score_margin_not_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            payload = json.loads(compare.read_text(encoding="utf-8"))
            payload["top_score_margin"] = 1
            compare.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-min-top-score-margin",
                    "2",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            applied = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(applied.get("final_status"), "FAIL")
            self.assertIn("top_score_margin_below_required", applied.get("reasons", []))

    def test_apply_fail_when_required_top_score_margin_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            payload = json.loads(compare.read_text(encoding="utf-8"))
            payload.pop("top_score_margin", None)
            compare.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-min-top-score-margin",
                    "2",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            applied = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(applied.get("final_status"), "FAIL")
            self.assertIn("top_score_margin_missing_when_required", applied.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
