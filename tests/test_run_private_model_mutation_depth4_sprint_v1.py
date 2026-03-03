import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunPrivateModelMutationDepth4SprintV1Tests(unittest.TestCase):
    def test_run_depth4_sprint_with_small_local_pool(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_private_model_mutation_depth4_sprint_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_root = root / "private_pool"
            model_root.mkdir(parents=True, exist_ok=True)
            (model_root / "Plant.mo").write_text(
                "model Plant\n  Real x;\nequation\n  der(x)= -x;\nend Plant;\n",
                encoding="utf-8",
            )
            baseline = root / "baseline_summary.json"
            baseline.write_text(
                json.dumps(
                    {
                        "generated_mutations": 4,
                        "reproducible_mutations": 4,
                        "mutations_per_failure_type": 2,
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "depth4_out"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_PRIVATE_MODEL_ROOTS": str(model_root),
                    "GATEFORGE_PRIVATE_BATCH_OUT_DIR": str(out_dir),
                    "GATEFORGE_BASELINE_SCALE_SUMMARY": str(baseline),
                    "GATEFORGE_TARGET_SCALES": "small,medium,large",
                    "GATEFORGE_FAILURE_TYPES": "simulate_error,model_check_error",
                    "GATEFORGE_MIN_DISCOVERED_MODELS": "1",
                    "GATEFORGE_MIN_ACCEPTED_MODELS": "1",
                    "GATEFORGE_MIN_ACCEPTED_LARGE_MODELS": "0",
                    "GATEFORGE_MIN_GENERATED_MUTATIONS": "8",
                    "GATEFORGE_MIN_MUTATION_PER_MODEL": "1",
                    "GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS": "0",
                },
                timeout=240,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            depth = json.loads((out_dir / "depth_upgrade_report.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("scale_gate_status"), "PASS")
            self.assertGreaterEqual(int(summary.get("mutations_per_failure_type", 0) or 0), 4)
            self.assertIn(depth.get("status"), {"PASS", "NEEDS_REVIEW"})


if __name__ == "__main__":
    unittest.main()
