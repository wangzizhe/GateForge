import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RealModelExecutablePoolV1Tests(unittest.TestCase):
    def test_build_executable_pool_filters_and_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models_dir = root / "models"
            models_dir.mkdir(parents=True, exist_ok=True)

            m1 = models_dir / "PlantA.mo"
            m1.write_text("model PlantA\n  Real x;\nequation\n  der(x)=-x;\nend PlantA;\n", encoding="utf-8")
            m1_dup = models_dir / "PlantA_copy.mo"
            m1_dup.write_text(m1.read_text(encoding="utf-8"), encoding="utf-8")
            m2 = models_dir / "GridLarge.mo"
            m2.write_text(
                "\n".join(
                    ["model GridLarge", "  Real x;", "  Real y;"]
                    + [f"  parameter Real p{i}={i};" for i in range(1, 120)]
                    + ["equation", "  der(x)=p1-p2;", "  der(y)=p3-p4;", "end GridLarge;"]
                )
                + "\n",
                encoding="utf-8",
            )
            pkg = models_dir / "package.mo"
            pkg.write_text("package Demo\nend Demo;\n", encoding="utf-8")
            partial = models_dir / "PartialProbe.mo"
            partial.write_text("partial model PartialProbe\n  Real x;\nend PartialProbe;\n", encoding="utf-8")

            registry = root / "intake_registry_rows.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m1", "asset_type": "model_source", "source_path": str(m1), "suggested_scale": "medium"},
                            {"model_id": "m1dup", "asset_type": "model_source", "source_path": str(m1_dup), "suggested_scale": "medium"},
                            {"model_id": "m2", "asset_type": "model_source", "source_path": str(m2), "suggested_scale": "large"},
                            {"model_id": "pkg", "asset_type": "model_source", "source_path": str(pkg), "suggested_scale": "small"},
                            {"model_id": "partial", "asset_type": "model_source", "source_path": str(partial), "suggested_scale": "small"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            out_registry = root / "executable_registry_rows.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_real_model_executable_pool_v1",
                    "--intake-registry-rows",
                    str(registry),
                    "--out-registry",
                    str(out_registry),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            exe_registry = json.loads(out_registry.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("raw_models", 0)), 5)
            self.assertEqual(int(summary.get("executable_unique_models", 0)), 2)
            self.assertEqual(int(summary.get("executable_large_models", 0)), 1)
            self.assertGreaterEqual(int(summary.get("duplicate_checksum_removed_count", 0)), 1)
            self.assertEqual(len(exe_registry.get("models") or []), 2)


if __name__ == "__main__":
    unittest.main()
