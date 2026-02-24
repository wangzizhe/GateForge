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
                    "explanation_quality": {
                        "score": 90,
                        "checks": {
                            "has_selection_priority": True,
                            "has_pairwise_rows": True,
                            "all_pairwise_have_margin": True,
                            "all_pairwise_have_profiles": True,
                            "pairwise_advantages_non_empty": True,
                        },
                    },
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
                    "decision_explanation_leaderboard": [
                        {
                            "profile": best_profile,
                            "leaderboard_rank": 1,
                            "pairwise_net_margin": 3,
                            "pairwise_against_others": [
                                {"challenger_profile": "industrial_strict", "margin": 3, "relation": "win"}
                            ],
                        }
                    ],
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
                        "top_score_margin": 3,
                        "explanation_quality": {"score": 100},
                        "decision_explanations": {
                            "best_vs_others": [
                                {
                                    "winner_profile": "default",
                                    # malformed: challenger_profile missing
                                    "score_margin": "3",  # malformed: should be int
                                }
                            ]
                        },
                        "decision_explanation_ranked": [
                            {
                                "reason": "top_score_margin",
                                "value": 3,
                                "weight": 100,
                                "note": "best profile leads by margin",
                            }
                        ],
                        "explanation_completeness": 100,
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

    def test_apply_fail_when_required_pairwise_net_margin_not_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            payload = json.loads(compare.read_text(encoding="utf-8"))
            payload["decision_explanation_leaderboard"][0]["pairwise_net_margin"] = 1
            compare.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-min-pairwise-net-margin",
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
            self.assertIn("pairwise_net_margin_below_required", applied.get("reasons", []))

    def test_apply_fail_when_required_pairwise_net_margin_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            payload = json.loads(compare.read_text(encoding="utf-8"))
            payload.pop("decision_explanation_leaderboard", None)
            compare.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-min-pairwise-net-margin",
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
            self.assertIn("pairwise_net_margin_missing_when_required", applied.get("reasons", []))

    def test_apply_fail_when_required_explanation_quality_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            payload = json.loads(compare.read_text(encoding="utf-8"))
            payload.pop("explanation_quality", None)
            compare.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-min-explanation-quality",
                    "80",
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
            self.assertIn("explanation_quality_missing_when_required", applied.get("reasons", []))
            self.assertTrue(applied.get("human_hints"))

    def test_apply_fail_when_required_explanation_quality_not_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            payload = json.loads(compare.read_text(encoding="utf-8"))
            payload["explanation_quality"] = {"score": 60}
            compare.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-min-explanation-quality",
                    "80",
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
            self.assertIn("explanation_quality_below_required", applied.get("reasons", []))
            self.assertTrue(applied.get("human_hints"))

    def test_apply_uses_policy_profile_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            payload = json.loads(compare.read_text(encoding="utf-8"))
            payload["top_score_margin"] = 2
            payload["explanation_quality"] = {"score": 80}
            compare.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--policy-profile",
                    "industrial_strict",
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
            self.assertEqual(applied.get("policy_profile"), "industrial_strict")
            self.assertIn("top_score_margin_below_required", applied.get("reasons", []))
            self.assertIn("explanation_quality_below_required", applied.get("reasons", []))
            self.assertEqual(applied.get("source_require_min_top_score_margin"), "policy_profile")
            self.assertEqual(applied.get("source_require_min_explanation_quality"), "policy_profile")

    def test_apply_cli_overrides_policy_profile_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            payload = json.loads(compare.read_text(encoding="utf-8"))
            payload["top_score_margin"] = 2
            payload["explanation_quality"] = {"score": 80}
            compare.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--policy-profile",
                    "industrial_strict",
                    "--require-min-top-score-margin",
                    "2",
                    "--require-min-explanation-quality",
                    "80",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            applied = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(applied.get("final_status"), "PASS")
            self.assertEqual(applied.get("source_require_min_top_score_margin"), "cli")
            self.assertEqual(applied.get("source_require_min_explanation_quality"), "cli")

    def test_apply_guardrail_drift_defaults_to_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            baseline_out = root / "baseline_apply.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")

            baseline_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--policy-profile",
                    "default",
                    "--out",
                    str(baseline_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(baseline_proc.returncode, 0, msg=baseline_proc.stderr or baseline_proc.stdout)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--policy-profile",
                    "industrial_strict",
                    "--baseline-apply-summary",
                    str(baseline_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            applied = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(applied.get("final_status"), "NEEDS_REVIEW")
            self.assertEqual(applied.get("apply_action"), "hold_for_review")
            self.assertTrue(applied.get("guardrail_drift_detected"))
            self.assertIn("guardrail_policy_hash_drift", applied.get("reasons", []))
            self.assertIn("guardrail_effective_guardrails_hash_drift", applied.get("reasons", []))

    def test_apply_guardrail_drift_strict_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            baseline_out = root / "baseline_apply.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")

            baseline_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--policy-profile",
                    "default",
                    "--out",
                    str(baseline_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(baseline_proc.returncode, 0, msg=baseline_proc.stderr or baseline_proc.stdout)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--policy-profile",
                    "industrial_strict",
                    "--baseline-apply-summary",
                    str(baseline_out),
                    "--strict-guardrail-drift",
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
            self.assertEqual(applied.get("apply_action"), "block")
            self.assertTrue(applied.get("strict_guardrail_drift"))
            self.assertIn("guardrail_policy_hash_drift", applied.get("reasons", []))

    def test_apply_guardrail_no_drift_with_same_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            baseline_out = root / "baseline_apply.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")

            baseline_proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--policy-profile",
                    "default",
                    "--out",
                    str(baseline_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(baseline_proc.returncode, 0, msg=baseline_proc.stderr or baseline_proc.stdout)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--policy-profile",
                    "default",
                    "--baseline-apply-summary",
                    str(baseline_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            applied = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(applied.get("final_status"), "PASS")
            self.assertFalse(applied.get("guardrail_drift_detected"))
            self.assertEqual(applied.get("reasons"), [])

    def test_apply_ranking_structure_default_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-ranking-explanation-structure",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            applied = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(applied.get("final_status"), "NEEDS_REVIEW")
            self.assertEqual(applied.get("apply_action"), "hold_for_review")
            self.assertIn("ranking_explanation_structure_invalid", applied.get("reasons", []))
            self.assertIsInstance(applied.get("ranking_explanation_structure_errors"), list)
            self.assertGreater(len(applied.get("ranking_explanation_structure_errors") or []), 0)

    def test_apply_ranking_structure_strict_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            compare = root / "compare.json"
            out = root / "apply.json"
            self._write_compare_summary(compare, status="PASS", best_decision="PASS")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_promote_apply",
                    "--compare-summary",
                    str(compare),
                    "--require-ranking-explanation-structure",
                    "--strict-ranking-explanation-structure",
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
            self.assertEqual(applied.get("apply_action"), "block")
            self.assertIn("ranking_explanation_structure_invalid", applied.get("reasons", []))

    def test_apply_ranking_structure_strict_pass_when_complete(self) -> None:
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
                        "top_score_margin": 3,
                        "explanation_quality": {"score": 100},
                        "decision_explanations": {
                            "best_vs_others": [
                                {
                                    "winner_profile": "default",
                                    "challenger_profile": "industrial_strict",
                                    "score_margin": 3,
                                    "tie_on_total_score": False,
                                    "winner_advantages": ["decision_component"],
                                    "score_breakdown_delta": {
                                        "decision_component": 100,
                                        "exit_component": 0,
                                        "reasons_component": 0,
                                        "recommended_component": 3,
                                        "total_score": 103,
                                    },
                                    "ranked_advantages": [
                                        {"component": "decision_component", "delta": 100},
                                        {"component": "recommended_component", "delta": 3},
                                    ],
                                }
                            ]
                        },
                        "decision_explanation_ranked": [
                            {
                                "reason": "top_score_margin",
                                "value": 3,
                                "weight": 100,
                                "note": "best profile leads by margin",
                            },
                            {
                                "reason": "best_reason",
                                "value": "highest_total_score",
                                "weight": 40,
                                "note": "selection rule",
                            },
                        ],
                        "explanation_completeness": 100,
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
                    "--require-ranking-explanation-structure",
                    "--strict-ranking-explanation-structure",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            applied = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(applied.get("final_status"), "PASS")
            self.assertEqual(applied.get("ranking_explanation_structure_errors"), [])

    def test_apply_ranking_structure_strict_fail_when_meta_missing(self) -> None:
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
                        "top_score_margin": 3,
                        "explanation_quality": {"score": 100},
                        "decision_explanations": {
                            "best_vs_others": [
                                {
                                    "winner_profile": "default",
                                    "challenger_profile": "industrial_strict",
                                    "score_margin": 3,
                                    "tie_on_total_score": False,
                                    "winner_advantages": ["decision_component"],
                                    "score_breakdown_delta": {
                                        "decision_component": 100,
                                        "exit_component": 0,
                                        "reasons_component": 0,
                                        "recommended_component": 3,
                                        "total_score": 103,
                                    },
                                    "ranked_advantages": [
                                        {"component": "decision_component", "delta": 100},
                                        {"component": "recommended_component", "delta": 3},
                                    ],
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
                    "--require-ranking-explanation-structure",
                    "--strict-ranking-explanation-structure",
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
            errors = applied.get("ranking_explanation_structure_errors") or []
            self.assertIn("decision_explanation_ranked_missing_or_empty", errors)
            self.assertIn("explanation_completeness_invalid", errors)


if __name__ == "__main__":
    unittest.main()
