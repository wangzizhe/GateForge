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
            self.assertIn(summary.get("profile"), {"balanced", "large_first"})
            self.assertIn(summary.get("quality_gate_status"), {"PASS", "NEEDS_REVIEW"})

    def test_run_modelica_open_source_bootstrap_large_first_profile(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_modelica_open_source_bootstrap_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_root = root / "source" / "Pkg"
            source_root.mkdir(parents=True, exist_ok=True)

            # 2 large-like and 1 medium-like models to satisfy large-first quality gate.
            for idx in range(1, 3):
                lines = [f"model Large{idx}", "  Real x;", "  Real y;"]
                lines.extend([f"  parameter Real p{i}={i};" for i in range(1, 170)])
                lines.extend(
                    [
                        "equation",
                        "  der(x)=p1-p2+p3-p4+p5-p6+p7;",
                        "  der(y)=p8-p9+p10-p11+p12-p13+p14;",
                        f"end Large{idx};",
                    ]
                )
                (source_root / f"Large{idx}.mo").write_text("\n".join(lines) + "\n", encoding="utf-8")
            (source_root / "Medium1.mo").write_text(
                "\n".join(
                    ["model Medium1", "  Real x;"]
                    + [f"  parameter Real k{i}={i};" for i in range(1, 90)]
                    + ["equation", "  der(x)=k1-k2+k3-k4+k5;", "end Medium1;"]
                )
                + "\n",
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
                                "scale_hint": "large",
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
                    "GATEFORGE_MODELICA_BOOTSTRAP_PROFILE": "large_first",
                    "GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_MODELS": "3",
                    "GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_LARGE_MODELS": "2",
                    "GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_LARGE_RATIO_PCT": "60",
                    "GATEFORGE_MAX_MODELS_PER_SOURCE": "10",
                },
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("profile"), "large_first")
            self.assertEqual(summary.get("quality_gate_status"), "PASS")
            self.assertGreaterEqual(int(summary.get("accepted_large_models", 0) or 0), 2)
            self.assertGreaterEqual(float(summary.get("accepted_large_ratio_pct", 0.0) or 0.0), 60.0)


if __name__ == "__main__":
    unittest.main()
