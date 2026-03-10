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

    def test_build_challenge_pack_carries_pack_metadata_and_category_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "A1.mo"
            model.write_text("model A1\nend A1;\n", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "u1", "scale": "small", "failure_type": "underconstrained_system", "category": "topology_wiring", "source_model_path": str(model), "mutated_model_path": str(model)},
                            {"task_id": "u2", "scale": "medium", "failure_type": "underconstrained_system", "category": "topology_wiring", "source_model_path": str(model), "mutated_model_path": str(model)},
                            {"task_id": "c1", "scale": "small", "failure_type": "connector_mismatch", "category": "topology_wiring", "source_model_path": str(model), "mutated_model_path": str(model)},
                            {"task_id": "c2", "scale": "medium", "failure_type": "connector_mismatch", "category": "topology_wiring", "source_model_path": str(model), "mutated_model_path": str(model)},
                            {"task_id": "i1", "scale": "small", "failure_type": "initialization_infeasible", "category": "initialization", "source_model_path": str(model), "mutated_model_path": str(model)},
                            {"task_id": "i2", "scale": "medium", "failure_type": "initialization_infeasible", "category": "initialization", "source_model_path": str(model), "mutated_model_path": str(model)},
                        ]
                    }
                ),
                encoding="utf-8",
            )
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
                    "--failure-types",
                    "underconstrained_system,connector_mismatch,initialization_infeasible",
                    "--required-categories",
                    "topology_wiring,initialization",
                    "--pack-id",
                    "agent_modelica_realism_pack_v1",
                    "--pack-version",
                    "v1",
                    "--pack-track",
                    "realism",
                    "--acceptance-scope",
                    "independent_validation",
                    "--baseline-off-success-at-k-pct",
                    "90",
                    "--target-min-off-success-pct",
                    "60",
                    "--target-max-off-success-pct",
                    "95",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "frozen_summary.json").read_text(encoding="utf-8"))
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("pack_track"), "realism")
            self.assertEqual(summary.get("acceptance_scope"), "independent_validation")
            self.assertEqual(int((summary.get("counts_by_category") or {}).get("topology_wiring") or 0), 4)
            self.assertEqual(int((summary.get("counts_by_category") or {}).get("initialization") or 0), 2)
            self.assertEqual(manifest.get("pack_id"), "agent_modelica_realism_pack_v1")
            self.assertEqual(manifest.get("pack_version"), "v1")


if __name__ == "__main__":
    unittest.main()
