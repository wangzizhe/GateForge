import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunPrivateModelMutationDepth6StabilityTripletV1Tests(unittest.TestCase):
    def test_run_stability_triplet_script_with_existing_only(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_private_model_mutation_depth6_stability_triplet_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            existing_dir = root / "existing_depth6"
            existing_dir.mkdir(parents=True, exist_ok=True)
            (existing_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "bundle_status": "PASS",
                        "scale_gate_status": "PASS",
                        "accepted_models": 1200,
                        "accepted_large_models": 300,
                        "generated_mutations": 20000,
                        "reproducible_mutations": 20000,
                        "mutations_per_failure_type": 6,
                    }
                ),
                encoding="utf-8",
            )
            (existing_dir / "intake_runner_accepted.json").write_text(
                json.dumps(
                    {
                        "rows": [
                            {"candidate_id": "m1", "model_path": str(existing_dir / "m1.mo"), "source_url": "https://x/m1", "expected_scale": "large"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (existing_dir / "intake_registry_rows.json").write_text(
                json.dumps(
                    {"models": [{"model_id": "m1", "asset_type": "model_source", "source_path": str(existing_dir / "m1.mo"), "suggested_scale": "large"}]}
                ),
                encoding="utf-8",
            )
            (existing_dir / "m1.mo").write_text("model M1\n Real x;\nequation\n der(x)= -x;\nend M1;\n", encoding="utf-8")

            out_dir = root / "out"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_DEPTH6_STABILITY_OUT_DIR": str(out_dir),
                    "GATEFORGE_STABILITY_WINDOW_SIZE": "1",
                    "GATEFORGE_STABILITY_INCLUDE_EXISTING": "1",
                    "GATEFORGE_EXISTING_DEPTH6_SCALE_SUMMARY": str(existing_dir / "summary.json"),
                },
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(payload.get("window_size", 0) or 0), 1)


if __name__ == "__main__":
    unittest.main()
