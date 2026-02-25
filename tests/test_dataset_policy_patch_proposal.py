import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPolicyPatchProposalTests(unittest.TestCase):
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
                            "suggested_action": "hold_release",
                            "suggested_policy_profile": "dataset_strict",
                            "confidence": 0.86,
                            "reasons": ["dataset_case_count_below_policy"],
                            "threshold_patch": {
                                "min_deduplicated_cases": 12,
                                "min_failure_case_rate": 0.2,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            policy.write_text(
                json.dumps(
                    {
                        "min_deduplicated_cases": 10,
                        "min_failure_case_rate": 0.15,
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_patch_proposal",
                    "--advisor-summary",
                    str(advisor),
                    "--policy-path",
                    str(policy),
                    "--proposal-id",
                    "dataset-patch-001",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("proposal_id"), "dataset-patch-001")
            self.assertEqual(payload.get("change_count"), 2)
            self.assertEqual(payload.get("policy_after", {}).get("min_deduplicated_cases"), 12)
            self.assertEqual(payload.get("policy_after", {}).get("min_failure_case_rate"), 0.2)

    def test_no_change_when_patch_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            advisor = root / "advisor.json"
            policy = root / "policy.json"
            out = root / "proposal.json"

            advisor.write_text(
                json.dumps(
                    {
                        "advice": {
                            "suggested_action": "keep",
                            "threshold_patch": {},
                        }
                    }
                ),
                encoding="utf-8",
            )
            policy.write_text(
                json.dumps({"min_deduplicated_cases": 10, "min_failure_case_rate": 0.2}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_patch_proposal",
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
            self.assertEqual(payload.get("changes"), [])


if __name__ == "__main__":
    unittest.main()
