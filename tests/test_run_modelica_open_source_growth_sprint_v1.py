import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunModelicaOpenSourceGrowthSprintV1Tests(unittest.TestCase):
    def test_run_growth_sprint_with_local_manifest(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_modelica_open_source_growth_sprint_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_root = root / "source" / "Base" / "A"
            source_root.mkdir(parents=True, exist_ok=True)
            (source_root / "Plant.mo").write_text(
                "model Plant\n  Real x;\nequation\n  der(x)= -x;\nend Plant;\n",
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_id": "local_demo",
                                "mode": "local",
                                "local_path": str(root / "source"),
                                "license": "BSD-3-Clause",
                                "scale_hint": "medium",
                                "package_roots": ["Base"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            out_dir = root / "growth_out"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_MODELICA_GROWTH_SPRINT_OUT_DIR": str(out_dir),
                    "GATEFORGE_MODELICA_SOURCE_MANIFEST": str(manifest),
                    "GATEFORGE_MODELICA_SOURCE_CACHE_ROOT": str(root / "cache"),
                    "GATEFORGE_MODELICA_EXPORT_ROOT": str(root / "exported"),
                    "GATEFORGE_MODELICA_BOOTSTRAP_FETCH": "0",
                    "GATEFORGE_MODELICA_BOOTSTRAP_PROFILE": "balanced",
                    "GATEFORGE_MAX_MODELS_PER_SOURCE": "20",
                    "GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_MODELS": "1",
                    "GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_LARGE_MODELS": "0",
                    "GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_LARGE_RATIO_PCT": "0",
                    "GATEFORGE_MANIFEST_EXPAND_MAX_SHARDS_PER_SOURCE": "3",
                    "GATEFORGE_MANIFEST_EXPAND_MIN_MO_FILES_PER_SHARD": "1",
                    "GATEFORGE_MIN_DISCOVERED_MODELS": "1",
                    "GATEFORGE_MIN_ACCEPTED_MODELS": "1",
                    "GATEFORGE_MIN_ACCEPTED_LARGE_MODELS": "0",
                    "GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT": "0",
                    "GATEFORGE_MIN_GENERATED_MUTATIONS": "4",
                    "GATEFORGE_MIN_MUTATION_PER_MODEL": "1",
                    "GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS": "0",
                    "GATEFORGE_MUTATIONS_PER_FAILURE_TYPE": "2",
                    "GATEFORGE_FAILURE_TYPES": "simulate_error,model_check_error",
                    "GATEFORGE_TARGET_SCALES": "small,medium,large",
                },
                timeout=240,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("bundle_status"), "PASS")
            self.assertIn(summary.get("scale_gate_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertGreaterEqual(int(summary.get("accepted_models", 0) or 0), 1)


if __name__ == "__main__":
    unittest.main()
