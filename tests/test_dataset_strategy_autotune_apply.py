import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetStrategyAutotuneApplyTests(unittest.TestCase):
    def test_apply_writes_selected_profile_config(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            approval = root / "approval.json"
            target = root / "active_strategy.json"
            out = root / "apply.json"
            advisor.write_text(
                json.dumps(
                    {
                        "advice": {
                            "suggested_policy_profile": "dataset_strict",
                            "suggested_action": "tighten_generation_controls",
                            "confidence": 0.91,
                        }
                    }
                ),
                encoding="utf-8",
            )
            approval.write_text(json.dumps({"decision": "approve", "reviewer": "human.reviewer"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_strategy_autotune_apply",
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("final_status"), "PASS")
            self.assertEqual(summary.get("apply_action"), "applied")
            active = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(active.get("active_dataset_strategy_profile"), "dataset_strict")

    def test_apply_needs_review_without_required_approval(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            out = root / "apply.json"
            advisor.write_text(
                json.dumps(
                    {
                        "advice": {
                            "suggested_policy_profile": "dataset_default",
                            "suggested_action": "keep",
                            "confidence": 0.9,
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_strategy_autotune_apply",
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("final_status"), "NEEDS_REVIEW")
            self.assertIn("approval_required", summary.get("reasons", []))

    def test_apply_needs_review_when_confidence_is_low(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            approval = root / "approval.json"
            out = root / "apply.json"
            advisor.write_text(
                json.dumps(
                    {
                        "advice": {
                            "suggested_policy_profile": "dataset_default",
                            "suggested_action": "keep",
                            "confidence": 0.4,
                        }
                    }
                ),
                encoding="utf-8",
            )
            approval.write_text(json.dumps({"decision": "approve", "reviewer": "human.reviewer"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_strategy_autotune_apply",
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
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("final_status"), "NEEDS_REVIEW")
            self.assertIn("advisor_confidence_below_apply_threshold", summary.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
