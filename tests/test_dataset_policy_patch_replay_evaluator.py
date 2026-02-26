import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPolicyPatchReplayEvaluatorTests(unittest.TestCase):
    def test_recommend_adopt_when_metrics_improve(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before_b = root / "before_b.json"
            after_b = root / "after_b.json"
            before_s = root / "before_s.json"
            after_s = root / "after_s.json"
            apply_s = root / "apply.json"
            out = root / "summary.json"

            before_b.write_text(json.dumps({"detection_rate_after": 0.78, "false_positive_rate_after": 0.11, "regression_rate_after": 0.2}), encoding="utf-8")
            after_b.write_text(json.dumps({"detection_rate_after": 0.85, "false_positive_rate_after": 0.08, "regression_rate_after": 0.14}), encoding="utf-8")
            before_s.write_text(json.dumps({"risks": ["a", "b", "c"]}), encoding="utf-8")
            after_s.write_text(json.dumps({"risks": ["a"]}), encoding="utf-8")
            apply_s.write_text(json.dumps({"final_status": "PASS"}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_patch_replay_evaluator",
                    "--before-benchmark",
                    str(before_b),
                    "--after-benchmark",
                    str(after_b),
                    "--before-snapshot",
                    str(before_s),
                    "--after-snapshot",
                    str(after_s),
                    "--patch-apply-summary",
                    str(apply_s),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("recommendation"), "ADOPT_PATCH")

    def test_recommend_rollback_when_metrics_worsen(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            before_b = root / "before_b.json"
            after_b = root / "after_b.json"
            before_s = root / "before_s.json"
            after_s = root / "after_s.json"
            apply_s = root / "apply.json"
            out = root / "summary.json"

            before_b.write_text(json.dumps({"detection_rate_after": 0.82, "false_positive_rate_after": 0.06, "regression_rate_after": 0.1}), encoding="utf-8")
            after_b.write_text(json.dumps({"detection_rate_after": 0.75, "false_positive_rate_after": 0.12, "regression_rate_after": 0.19}), encoding="utf-8")
            before_s.write_text(json.dumps({"risks": ["a"]}), encoding="utf-8")
            after_s.write_text(json.dumps({"risks": ["a", "b", "c", "d"]}), encoding="utf-8")
            apply_s.write_text(json.dumps({"final_status": "FAIL"}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_patch_replay_evaluator",
                    "--before-benchmark",
                    str(before_b),
                    "--after-benchmark",
                    str(after_b),
                    "--before-snapshot",
                    str(before_s),
                    "--after-snapshot",
                    str(after_s),
                    "--patch-apply-summary",
                    str(apply_s),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertEqual(payload.get("recommendation"), "ROLLBACK_OR_REVISE")


if __name__ == "__main__":
    unittest.main()
