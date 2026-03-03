import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetScaleCheckpointFeedbackGateV1Tests(unittest.TestCase):
    def test_feedback_gate_generates_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            checkpoint = root / "checkpoint.json"
            history = root / "history.json"
            trend = root / "trend.json"
            velocity = root / "velocity.json"
            out = root / "summary.json"
            checkpoint.write_text(json.dumps({"status": "NEEDS_REVIEW", "milestone_score": 78.0}), encoding="utf-8")
            history.write_text(json.dumps({"status": "NEEDS_REVIEW", "avg_total_p0_actions": 2.5}), encoding="utf-8")
            trend.write_text(json.dumps({"status": "NEEDS_REVIEW", "trend": {"delta_avg_total_p0_actions": 0.5}}), encoding="utf-8")
            velocity.write_text(json.dumps({"status": "PASS", "on_track_within_horizon": False, "model_gap_weeks_to_close": 20, "mutation_gap_weeks_to_close": 18}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_checkpoint_feedback_gate_v1",
                    "--weekly-scale-milestone-checkpoint-summary",
                    str(checkpoint),
                    "--scale-action-backlog-history-summary",
                    str(history),
                    "--scale-action-backlog-trend-summary",
                    str(trend),
                    "--scale-velocity-forecast-summary",
                    str(velocity),
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
            self.assertIn(payload.get("adjusted_checkpoint_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})

    def test_feedback_gate_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_scale_checkpoint_feedback_gate_v1",
                    "--weekly-scale-milestone-checkpoint-summary",
                    str(root / "missing_checkpoint.json"),
                    "--scale-action-backlog-history-summary",
                    str(root / "missing_history.json"),
                    "--scale-action-backlog-trend-summary",
                    str(root / "missing_trend.json"),
                    "--scale-velocity-forecast-summary",
                    str(root / "missing_velocity.json"),
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
