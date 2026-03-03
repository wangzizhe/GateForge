import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationReproDepthGuardV1Tests(unittest.TestCase):
    def test_repro_depth_guard_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            observations = root / "observations.json"
            plan = root / "plan.json"
            out = root / "summary.json"

            mutations = []
            for midx in range(1, 4):
                model_id = f"m{midx}"
                scale = "large" if midx == 1 else "medium"
                for j in range(1, 7):
                    mutations.append(
                        {
                            "mutation_id": f"{model_id}_mut_{j}",
                            "target_model_id": model_id,
                            "target_scale": scale,
                        }
                    )
            manifest.write_text(json.dumps({"mutations": mutations}), encoding="utf-8")

            obs = []
            for row in mutations:
                obs.append(
                    {
                        "mutation_id": row["mutation_id"],
                        "execution_status": "EXECUTED",
                        "final_return_code": 0,
                    }
                )
            observations.write_text(json.dumps({"observations": obs}), encoding="utf-8")
            plan.write_text(json.dumps({"selected_model_ids": ["m1", "m2", "m3"]}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_repro_depth_guard_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(observations),
                    "--selection-plan",
                    str(plan),
                    "--min-reproducible-mutations-per-model",
                    "4",
                    "--min-large-model-reproducible-mutations-per-model",
                    "4",
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
            self.assertEqual(int(payload.get("tracked_models", 0)), 3)

    def test_repro_depth_guard_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_repro_depth_guard_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--mutation-raw-observations",
                    str(root / "missing_observations.json"),
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
