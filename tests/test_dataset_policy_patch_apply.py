import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPolicyPatchApplyTests(unittest.TestCase):
    def _write_proposal(self, path: Path, target_policy: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": "dataset-patch-001",
                    "target_policy_path": str(target_policy),
                    "policy_after": {
                        "min_deduplicated_cases": 12,
                        "min_failure_case_rate": 0.2,
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_needs_review_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "policy.json"
            policy.write_text(json.dumps({"min_deduplicated_cases": 10}), encoding="utf-8")
            proposal = root / "proposal.json"
            out = root / "apply.json"
            self._write_proposal(proposal, policy)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_patch_apply",
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

    def test_apply_passes_with_approve_and_apply_flag(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "policy.json"
            policy.write_text(json.dumps({"min_deduplicated_cases": 10}), encoding="utf-8")
            proposal = root / "proposal.json"
            approval = root / "approval.json"
            out = root / "apply.json"
            self._write_proposal(proposal, policy)
            approval.write_text(json.dumps({"decision": "approve", "reviewer": "human.reviewer"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_patch_apply",
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
            updated = json.loads(policy.read_text(encoding="utf-8"))
            self.assertEqual(updated.get("min_deduplicated_cases"), 12)

    def test_reject_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "policy.json"
            policy.write_text(json.dumps({"min_deduplicated_cases": 10}), encoding="utf-8")
            proposal = root / "proposal.json"
            approval = root / "approval.json"
            out = root / "apply.json"
            self._write_proposal(proposal, policy)
            approval.write_text(json.dumps({"decision": "reject", "reviewer": "human.reviewer"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_patch_apply",
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


if __name__ == "__main__":
    unittest.main()

