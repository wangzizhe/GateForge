import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetReplayQualityGuardTests(unittest.TestCase):
    def test_guard_pass_when_samples_and_stability_ok(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            replay = root / "replay.json"
            before_b = root / "before_b.json"
            after_b = root / "after_b.json"
            out = root / "summary.json"

            replay.write_text(
                json.dumps({"delta": {"detection_rate": 0.04, "false_positive_rate": -0.01, "regression_rate": -0.03, "review_load": -1}}),
                encoding="utf-8",
            )
            before_b.write_text(json.dumps({"total_cases_after": 28}), encoding="utf-8")
            after_b.write_text(json.dumps({"total_cases_after": 31}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_replay_quality_guard",
                    "--replay-evaluator",
                    str(replay),
                    "--before-benchmark",
                    str(before_b),
                    "--after-benchmark",
                    str(after_b),
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
            self.assertEqual(payload.get("confidence_level"), "high")

    def test_guard_needs_review_when_samples_low(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            replay = root / "replay.json"
            before_b = root / "before_b.json"
            after_b = root / "after_b.json"
            out = root / "summary.json"

            replay.write_text(
                json.dumps({"delta": {"detection_rate": 0.02, "false_positive_rate": 0.0, "regression_rate": 0.0, "review_load": 0}}),
                encoding="utf-8",
            )
            before_b.write_text(json.dumps({"total_cases_after": 10}), encoding="utf-8")
            after_b.write_text(json.dumps({"total_cases_after": 12}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_replay_quality_guard",
                    "--replay-evaluator",
                    str(replay),
                    "--before-benchmark",
                    str(before_b),
                    "--after-benchmark",
                    str(after_b),
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
            self.assertIn("sample_size_before_insufficient", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
