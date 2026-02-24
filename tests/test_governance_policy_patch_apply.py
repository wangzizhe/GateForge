import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePolicyPatchApplyTests(unittest.TestCase):
    def _write_proposal(self, path: Path, target_policy: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": "patch-001",
                    "target_policy_path": str(target_policy),
                    "changes": [
                        {
                            "key": "require_min_top_score_margin",
                            "old": 1,
                            "new": 2,
                        }
                    ],
                    "policy_after": {
                        "version": "0.1.0",
                        "require_ranking_explanation": False,
                        "require_min_top_score_margin": 2,
                        "require_min_explanation_quality": 85,
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_apply_needs_review_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "policy.json"
            policy.write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
            proposal = root / "proposal.json"
            out = root / "apply.json"
            self._write_proposal(proposal, policy)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_apply",
                    "--proposal",
                    str(proposal),
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
            self.assertIn("approval_required", payload.get("reasons", []))
            self.assertEqual(payload.get("approval_profile"), "default")
            self.assertIsInstance(payload.get("impact_preview"), list)

    def test_apply_fails_on_reject(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "policy.json"
            policy.write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
            proposal = root / "proposal.json"
            approval = root / "approval.json"
            out = root / "apply.json"
            self._write_proposal(proposal, policy)
            approval.write_text(json.dumps({"decision": "reject", "reviewer": "human.reviewer"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_apply",
                    "--proposal",
                    str(proposal),
                    "--approval",
                    str(approval),
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
            self.assertIn("approval_rejected", payload.get("reasons", []))
            self.assertIn("reject", payload.get("approval_decisions", []))

    def test_apply_writes_policy_on_approve_with_apply_flag(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "version": "0.1.0",
                        "require_ranking_explanation": False,
                        "require_min_top_score_margin": 1,
                        "require_min_explanation_quality": 70,
                    }
                ),
                encoding="utf-8",
            )
            proposal = root / "proposal.json"
            approval = root / "approval.json"
            out = root / "apply.json"
            self._write_proposal(proposal, policy)
            approval.write_text(json.dumps({"decision": "approve", "reviewer": "human.reviewer"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_apply",
                    "--proposal",
                    str(proposal),
                    "--approval",
                    str(approval),
                    "--apply",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("final_status"), "PASS")
            self.assertTrue(payload.get("applied"))
            self.assertEqual(payload.get("approval_profile"), "default")
            updated = json.loads(policy.read_text(encoding="utf-8"))
            self.assertEqual(updated.get("require_min_top_score_margin"), 2)
            self.assertEqual(updated.get("require_min_explanation_quality"), 85)
            self.assertEqual((payload.get("impact_preview") or [])[0].get("expected_effect"), "stricter_compare_margin_gate")

    def test_dual_reviewer_profile_requires_two_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "policy.json"
            proposal = root / "proposal.json"
            approval = root / "approval.json"
            out = root / "apply.json"
            policy.write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
            self._write_proposal(proposal, policy)
            approval.write_text(json.dumps({"decision": "approve", "reviewer": "a"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_apply",
                    "--proposal",
                    str(proposal),
                    "--approval",
                    str(approval),
                    "--approval-profile",
                    "dual_reviewer",
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
            self.assertIn("approval_count_insufficient", payload.get("reasons", []))

    def test_dual_reviewer_profile_passes_with_two_unique_approvals_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "policy.json"
            proposal = root / "proposal.json"
            approval = root / "approval.json"
            out = root / "apply.json"
            policy.write_text(json.dumps({"version": "0.1.0", "require_min_top_score_margin": 1}), encoding="utf-8")
            self._write_proposal(proposal, policy)
            approval.write_text(
                json.dumps(
                    {
                        "approvals": [
                            {"decision": "approve", "reviewer": "r1"},
                            {"decision": "approve", "reviewer": "r2"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_apply",
                    "--proposal",
                    str(proposal),
                    "--approval",
                    str(approval),
                    "--approval-profile",
                    "dual_reviewer",
                    "--apply",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("final_status"), "PASS")
            self.assertEqual(payload.get("approval_profile"), "dual_reviewer")
            self.assertEqual(payload.get("approvals_count"), 2)
            self.assertEqual(payload.get("unique_reviewers_count"), 2)

    def test_preview_only_outputs_preview_without_apply(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "policy.json"
            proposal = root / "proposal.json"
            out = root / "preview.json"
            policy.write_text(json.dumps({"version": "0.1.0", "require_min_top_score_margin": 1}), encoding="utf-8")
            self._write_proposal(proposal, policy)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_patch_apply",
                    "--proposal",
                    str(proposal),
                    "--preview-only",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("final_status"), "PREVIEW")
            self.assertEqual(payload.get("apply_action"), "preview_only")
            self.assertFalse(payload.get("applied"))
            self.assertIn("preview_only_no_apply", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
