import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaOpenSourceHarvestV1Tests(unittest.TestCase):
    def test_harvest_local_sources(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "source_a" / "Pkg"
            src.mkdir(parents=True, exist_ok=True)
            (src / "A.mo").write_text(
                "model A\n  Real x;\nequation\n  der(x)= -x;\nend A;\n",
                encoding="utf-8",
            )
            (src / "B.mo").write_text(
                "model B\n  Real y;\nequation\n  der(y)= -0.1*y;\nend B;\n",
                encoding="utf-8",
            )

            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_id": "source_a",
                                "mode": "local",
                                "local_path": str(root / "source_a"),
                                "license": "BSD-3-Clause",
                                "scale_hint": "medium",
                                "package_roots": ["Pkg"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            catalog_out = root / "catalog.json"
            summary_out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_open_source_harvest_v1",
                    "--source-manifest",
                    str(manifest),
                    "--source-cache-root",
                    str(root / "cache"),
                    "--export-root",
                    str(root / "exported"),
                    "--catalog-out",
                    str(catalog_out),
                    "--out",
                    str(summary_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(summary_out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(int(summary.get("total_candidates", 0) or 0), 2)
            catalog = json.loads(catalog_out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(catalog.get("candidates") or []), 2)

    def test_harvest_git_source_needs_review_when_fetch_off(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_id": "missing_repo",
                                "mode": "git",
                                "repo_url": "https://example.com/does-not-exist.git",
                                "ref": "main",
                                "license": "BSD-3-Clause",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            summary_out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_open_source_harvest_v1",
                    "--source-manifest",
                    str(manifest),
                    "--source-cache-root",
                    str(root / "cache"),
                    "--export-root",
                    str(root / "exported"),
                    "--catalog-out",
                    str(root / "catalog.json"),
                    "--out",
                    str(summary_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(summary_out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertEqual(int(summary.get("total_candidates", 0) or 0), 0)


if __name__ == "__main__":
    unittest.main()
