import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPromotionCandidateApplyTests(unittest.TestCase):
    def test_apply_writes_selected_promotion_state(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            approval = root / "approval.json"
            target = root / "active_promotion.json"
            out = root / "apply.json"
            advisor.write_text(
                json.dumps({"advice": {"decision": "PROMOTE", "action": "promote_candidate", "confidence": 0.9}}),
                encoding="utf-8",
            )
            approval.write_text(json.dumps({"decision": "approve", "reviewer": "human.reviewer"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_candidate_apply",
                    "--advisor-summary",
                    str(advisor),
                    "--approval",
                    str(approval),
                    "--apply",
                    "--target-state",
                    str(target),
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
            state = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(state.get("active_dataset_promotion_decision"), "PROMOTE")

    def test_apply_needs_review_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            out = root / "apply.json"
            advisor.write_text(
                json.dumps({"advice": {"decision": "PROMOTE", "action": "promote_candidate", "confidence": 0.9}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_candidate_apply",
                    "--advisor-summary",
                    str(advisor),
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
            self.assertEqual(payload.get("final_status"), "NEEDS_REVIEW")
            self.assertIn("approval_required", payload.get("reasons", []))

    def test_apply_blocks_non_promote_decision_by_policy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            approval = root / "approval.json"
            out = root / "apply.json"
            advisor.write_text(
                json.dumps({"advice": {"decision": "HOLD", "action": "hold_for_review", "confidence": 0.9}}),
                encoding="utf-8",
            )
            approval.write_text(json.dumps({"decision": "approve", "reviewer": "human.reviewer"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_promotion_candidate_apply",
                    "--advisor-summary",
                    str(advisor),
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
            self.assertEqual(payload.get("final_status"), "NEEDS_REVIEW")
            self.assertIn("decision_not_promote", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
