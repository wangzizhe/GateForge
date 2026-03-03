import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MutationModelMaterializerV1Tests(unittest.TestCase):
    def test_materialize_mutants_as_real_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models_dir = root / "models"
            models_dir.mkdir(parents=True, exist_ok=True)

            large = models_dir / "LargePlant.mo"
            large.write_text(
                "\n".join(
                    ["model LargePlant", "  Real x;", "  Real y;"]
                    + [f"  parameter Real p{i}={i};" for i in range(1, 140)]
                    + ["equation", "  der(x)=p1-p2+p3;", "  der(y)=p4-p5+p6;", "end LargePlant;"]
                )
                + "\n",
                encoding="utf-8",
            )
            medium = models_dir / "MediumPlant.mo"
            medium.write_text(
                "model MediumPlant\n  Real x;\nequation\n  der(x)=-x;\nend MediumPlant;\n",
                encoding="utf-8",
            )

            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m_large", "asset_type": "model_source", "source_path": str(large), "suggested_scale": "large"},
                            {"model_id": "m_medium", "asset_type": "model_source", "source_path": str(medium), "suggested_scale": "medium"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            manifest = root / "mutation_manifest.json"
            out = root / "summary.json"
            mutant_root = root / "mutants"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_model_materializer_v1",
                    "--model-registry",
                    str(registry),
                    "--target-scales",
                    "large,medium",
                    "--failure-types",
                    "simulate_error,model_check_error",
                    "--mutations-per-failure-type",
                    "2",
                    "--max-models",
                    "2",
                    "--mutant-root",
                    str(mutant_root),
                    "--manifest-out",
                    str(manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("selected_models", 0)), 2)
            self.assertEqual(int(summary.get("total_mutations", 0)), 8)
            self.assertEqual(int(summary.get("materialized_mutations", 0)), 8)

            rows = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
            self.assertEqual(len(rows), 8)
            for row in rows[:4]:
                mpath = Path(str(row.get("mutated_model_path") or ""))
                self.assertTrue(mpath.exists(), msg=str(mpath))
                text = mpath.read_text(encoding="utf-8")
                self.assertIn("GateForge mutation", text)
                self.assertTrue(str(row.get("repro_command") or "").startswith("python3 -c "))


if __name__ == "__main__":
    unittest.main()
