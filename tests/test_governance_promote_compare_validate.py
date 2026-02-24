import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.governance_promote_compare_validate import validate_compare_summary


def _complete_payload() -> dict:
    return {
        "status": "PASS",
        "best_profile": "default",
        "best_decision": "PASS",
        "top_score_margin": 4,
        "decision_explanations": {
            "selection_priority": ["total_score", "decision"],
            "best_vs_others": [
                {
                    "winner_profile": "default",
                    "challenger_profile": "industrial_strict",
                    "score_margin": 4,
                    "tie_on_total_score": False,
                    "winner_advantages": ["decision_component"],
                    "score_breakdown_delta": {
                        "decision_component": 100,
                        "exit_component": 0,
                        "reasons_component": 0,
                        "recommended_component": 1,
                        "total_score": 101,
                    },
                    "ranked_advantages": [{"component": "decision_component", "delta": 100}],
                }
            ],
        },
        "decision_explanation_leaderboard": [
            {"profile": "default", "pairwise_net_margin": 4}
        ],
        "decision_explanation_ranked": [
            {"reason": "top_score_margin", "weight": 100, "value": 4},
            {"reason": "best_reason", "weight": 10, "value": "highest_total_score"},
        ],
        "decision_explanation_ranking_details": {
            "top_driver": "top_score_margin",
            "numeric_reason_count": 1,
            "drivers": [
                {
                    "rank": 1,
                    "reason": "top_score_margin",
                    "weight": 100,
                    "value": 4,
                    "impact_score": 400,
                    "impact_share_pct": 100.0,
                }
            ],
        },
        "explanation_completeness": 100,
        "explanation_quality": {"score": 100},
    }


class GovernancePromoteCompareValidateTests(unittest.TestCase):
    def test_validate_apply_ready_pass(self) -> None:
        errors = validate_compare_summary(_complete_payload(), require_apply_ready=True)
        self.assertEqual(errors, [])

    def test_validate_apply_ready_fail_on_missing_pairwise_net_margin(self) -> None:
        payload = _complete_payload()
        payload["decision_explanation_leaderboard"] = [{"profile": "default"}]
        errors = validate_compare_summary(payload, require_apply_ready=True)
        self.assertIn("decision_explanation_leaderboard_pairwise_net_margin_invalid", errors)

    def test_validate_non_pass_only_checks_status(self) -> None:
        payload = {"status": "NEEDS_REVIEW"}
        errors = validate_compare_summary(payload, require_apply_ready=True)
        self.assertEqual(errors, [])

    def test_cli_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "compare.json"
            p.write_text(json.dumps(_complete_payload()), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.governance_promote_compare_validate", "--in", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_cli_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "compare_bad.json"
            payload = _complete_payload()
            payload["decision_explanation_ranking_details"] = {}
            p.write_text(json.dumps(payload), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.governance_promote_compare_validate", "--in", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("status", proc.stdout)


if __name__ == "__main__":
    unittest.main()
