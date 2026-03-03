import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunModelicaOpenSourceBootstrapV1Tests(unittest.TestCase):
    def test_run_modelica_open_source_bootstrap_with_local_manifest(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_modelica_open_source_bootstrap_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_root = root / "source" / "Pkg"
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
                                "package_roots": ["Pkg"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            out_dir = root / "out"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_MODELICA_SOURCE_MANIFEST": str(manifest),
                    "GATEFORGE_MODELICA_BOOTSTRAP_FETCH": "0",
                    "GATEFORGE_MODELICA_BOOTSTRAP_OUT_DIR": str(out_dir),
                    "GATEFORGE_MODELICA_SOURCE_CACHE_ROOT": str(root / "cache"),
                    "GATEFORGE_MODELICA_EXPORT_ROOT": str(root / "exported"),
                },
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertIn(summary.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(int(summary.get("accepted_models", 0) or 0), 1)


if __name__ == "__main__":
    unittest.main()
