import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetPolicyExperimentRunnerTests(unittest.TestCase):
    def test_runner_builds_ranked_experiments(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            replay = root / "replay.json"
            guard = root / "guard.json"
            advisor = root / "advisor.json"
            moat = root / "moat.json"
            out = root / "summary.json"

            replay.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "evaluation_score": 5,
                        "delta": {
                            "detection_rate": 0.03,
                            "false_positive_rate": -0.01,
                            "regression_rate": -0.02,
                            "review_load": -1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            guard.write_text(json.dumps({"status": "PASS", "confidence_level": "high"}), encoding="utf-8")
            advisor.write_text(json.dumps({"advice": {"suggested_action": "tighten"}}), encoding="utf-8")
            moat.write_text(json.dumps({"metrics": {"moat_score": 66.8}}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_experiment_runner",
                    "--policy-patch-replay-evaluator",
                    str(replay),
                    "--replay-quality-guard",
                    str(guard),
                    "--failure-policy-patch-advisor",
                    str(advisor),
                    "--moat-trend-snapshot",
                    str(moat),
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
            self.assertTrue(payload.get("recommended_experiment_id"))
            experiments = payload.get("experiments") if isinstance(payload.get("experiments"), list) else []
            self.assertGreaterEqual(len(experiments), 3)
            self.assertGreaterEqual(
                float(experiments[0].get("experiment_score", 0.0)),
                float(experiments[1].get("experiment_score", 0.0)),
            )

    def test_runner_fails_when_replay_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_policy_experiment_runner",
                    "--policy-patch-replay-evaluator",
                    str(root / "missing.json"),
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
            self.assertIn("replay_evaluator_missing", payload.get("reasons", []))


if __name__ == "__main__":
    unittest.main()
