import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePolicyPatchProposalTests(unittest.TestCase):
    def test_builds_patch_from_advisor_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            policy = root / "policy.json"
            out = root / "proposal.json"
            advisor.write_text(
                json.dumps(
                    {
                        "advice": {
                            "suggested_policy_profile": "industrial_strict",
                            "confidence": 0.81,
                            "reasons": ["mismatch_volume_increasing"],
                            "why_now": {"summary": "signals", "urgency": "high"},
                            "recommendation_scorecard": {"impact": "high", "priority": "urgent"},
                            "ranking_driver_signal": {
                                "top_driver": "component_delta:recommended_component",
                                "top_driver_impact_share_pct": 72.2,
                                "top_driver_value": 3,
                            },
                            "threshold_patch": {
                                "require_min_top_score_margin": 2,
                                "require_min_pairwise_net_margin": 3,
                                "require_min_explanation_quality": 85,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            policy.write_text(
                json.dumps(
                    {
                        "version": "0.1.0",
                        "require_ranking_explanation": False,
                        "require_min_top_score_margin": 1,
                        "require_min_pairwise_net_margin": 1,
                        "require_min_explanation_quality": 70,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_proposal",
                    "--advisor-summary",
                    str(advisor),
                    "--policy-path",
                    str(policy),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("change_count"), 3)
            after = payload.get("policy_after", {})
            self.assertEqual(after.get("require_min_top_score_margin"), 2)
            self.assertEqual(after.get("require_min_pairwise_net_margin"), 3)
            self.assertEqual(after.get("require_min_explanation_quality"), 85)
            self.assertEqual(payload.get("approval_status"), "PENDING")
            self.assertEqual((payload.get("advisor_why_now") or {}).get("urgency"), "high")
            self.assertEqual((payload.get("advisor_recommendation_scorecard") or {}).get("priority"), "urgent")
            self.assertEqual(
                (payload.get("advisor_ranking_driver_signal") or {}).get("top_driver"),
                "component_delta:recommended_component",
            )
            recommendation = payload.get("approval_recommendation") or {}
            self.assertEqual(recommendation.get("approval_profile"), "dual_reviewer")
            self.assertEqual(recommendation.get("required_approvals"), 2)

    def test_no_change_when_threshold_patch_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            policy = root / "policy.json"
            out = root / "proposal.json"
            advisor.write_text(json.dumps({"advice": {"threshold_patch": {}}}), encoding="utf-8")
            policy.write_text(
                json.dumps(
                    {
                        "version": "0.1.0",
                        "require_ranking_explanation": False,
                        "require_min_top_score_margin": 1,
                        "require_min_pairwise_net_margin": 1,
                        "require_min_explanation_quality": 70,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_proposal",
                    "--advisor-summary",
                    str(advisor),
                    "--policy-path",
                    str(policy),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("change_count"), 0)


if __name__ == "__main__":
    unittest.main()
