import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaL4ChallengePackV0Tests(unittest.TestCase):
    def _taskset_payload(self, model_path: str) -> dict:
        return {
            "tasks": [
                {"task_id": "a1", "scale": "small", "failure_type": "model_check_error", "source_model_path": model_path, "mutated_model_path": model_path},
                {"task_id": "a2", "scale": "medium", "failure_type": "model_check_error", "source_model_path": model_path, "mutated_model_path": model_path},
                {"task_id": "b1", "scale": "small", "failure_type": "simulate_error", "source_model_path": model_path, "mutated_model_path": model_path},
                {"task_id": "b2", "scale": "medium", "failure_type": "simulate_error", "source_model_path": model_path, "mutated_model_path": model_path},
                {"task_id": "c1", "scale": "small", "failure_type": "semantic_regression", "source_model_path": model_path, "mutated_model_path": model_path},
                {"task_id": "c2", "scale": "medium", "failure_type": "semantic_regression", "source_model_path": model_path, "mutated_model_path": model_path},
            ]
        }

    def test_build_challenge_pack_pass_with_baseline_in_range(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "A1.mo"
            model.write_text("model A1\nend A1;\n", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps(self._taskset_payload(str(model))), encoding="utf-8")
            out_dir = root / "pack"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_l4_challenge_pack_v0",
                    "--taskset-in",
                    str(taskset),
                    "--out-dir",
                    str(out_dir),
                    "--baseline-off-success-at-k-pct",
                    "75",
                    "--target-min-off-success-pct",
                    "60",
                    "--target-max-off-success-pct",
                    "90",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "frozen_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_selected_tasks") or 0), 6)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("status"), "PASS")
            self.assertTrue((out_dir / "taskset_frozen.json").exists())
            self.assertTrue((out_dir / "selection_config.json").exists())
            self.assertTrue((out_dir / "sha256.json").exists())

    def test_build_challenge_pack_needs_review_when_baseline_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "A1.mo"
            model.write_text("model A1\nend A1;\n", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps(self._taskset_payload(str(model))), encoding="utf-8")
            out_dir = root / "pack"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_l4_challenge_pack_v0",
                    "--taskset-in",
                    str(taskset),
                    "--out-dir",
                    str(out_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "frozen_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertIn("baseline_off_success_at_k_missing", set(summary.get("reasons") or []))


if __name__ == "__main__":
    unittest.main()
