import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetFamilyGapActionPlanV1Tests(unittest.TestCase):
    def test_family_gap_plan_generates_actions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            family = root / "family.json"
            checkpoint = root / "checkpoint.json"
            out = root / "summary.json"
            family.write_text(
                json.dumps(
                    {
                        "families": [
                            {"family": "fluid", "model_count": 1, "large_ratio": 0.0},
                            {"family": "thermal", "model_count": 4, "large_ratio": 0.1},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            checkpoint.write_text(json.dumps({"milestone_grade": "C"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_family_gap_action_plan_v1",
                    "--real-model-family-coverage-board-summary",
                    str(family),
                    "--weekly-scale-milestone-checkpoint-summary",
                    str(checkpoint),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(int(payload.get("total_actions", 0)), 1)

    def test_family_gap_plan_fail_when_missing_family_board(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_family_gap_action_plan_v1",
                    "--real-model-family-coverage-board-summary",
                    str(root / "missing_family.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
