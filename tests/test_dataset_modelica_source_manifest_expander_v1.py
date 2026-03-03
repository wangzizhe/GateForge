import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ModelicaSourceManifestExpanderV1Tests(unittest.TestCase):
    def test_expands_local_source_into_shards(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo = root / "repo"
            (repo / "Base" / "A").mkdir(parents=True, exist_ok=True)
            (repo / "Base" / "B").mkdir(parents=True, exist_ok=True)

            (repo / "Base" / "A" / "A1.mo").write_text("model A1\nend A1;\n", encoding="utf-8")
            (repo / "Base" / "A" / "A2.mo").write_text("model A2\nend A2;\n", encoding="utf-8")
            (repo / "Base" / "B" / "B1.mo").write_text("model B1\nend B1;\n", encoding="utf-8")

            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_id": "demo_repo",
                                "mode": "local",
                                "local_path": str(repo),
                                "license": "BSD-3-Clause",
                                "scale_hint": "medium",
                                "package_roots": ["Base"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            out_manifest = root / "expanded_manifest.json"
            out_summary = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_source_manifest_expander_v1",
                    "--source-manifest",
                    str(manifest),
                    "--source-cache-root",
                    str(root / "cache"),
                    "--max-shards-per-source",
                    "4",
                    "--min-mo-files-per-shard",
                    "1",
                    "--out",
                    str(out_manifest),
                    "--summary-out",
                    str(out_summary),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            summary = json.loads(out_summary.read_text(encoding="utf-8"))
            expanded = json.loads(out_manifest.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("added_sources_count", 0)), 1)
            self.assertGreater(int(summary.get("expanded_sources", 0)), int(summary.get("base_sources", 0)))
            self.assertGreater(len(expanded.get("sources", [])), 1)


if __name__ == "__main__":
    unittest.main()
