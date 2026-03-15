import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def _write_model(path: Path, model_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"model {model_name}",
                "  Modelica.Blocks.Sources.Constant src(k=1);",
                "  Modelica.Blocks.Math.Gain gain(k=2);",
                "equation",
                "  connect(src.y, gain.u);",
                f"end {model_name};",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _manifest(root: Path) -> Path:
    liba = root / "LibA"
    libb = root / "LibB"
    for path in (liba / "A.mo", liba / "B.mo", libb / "C.mo", libb / "D.mo"):
        _write_model(path, path.stem)
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "agent_modelica_unknown_library_pool_manifest_v1",
                "libraries": [
                    {
                        "library_id": "liba",
                        "package_name": "LibA",
                        "source_library": "LibA",
                        "license_provenance": "MIT",
                        "local_path": str(liba),
                        "accepted_source_path": str(liba),
                        "domain": "controls",
                        "component_interface_hints": ["gain"],
                        "connector_semantic_hints": ["u", "y"],
                        "allowed_models": [
                            {"model_id": "a", "qualified_model_name": "LibA.A", "model_path": str(liba / "A.mo"), "scale_hint": "small"},
                            {"model_id": "b", "qualified_model_name": "LibA.B", "model_path": str(liba / "B.mo"), "scale_hint": "small"}
                        ]
                    },
                    {
                        "library_id": "libb",
                        "package_name": "LibB",
                        "source_library": "LibB",
                        "license_provenance": "MIT",
                        "local_path": str(libb),
                        "accepted_source_path": str(libb),
                        "domain": "signals",
                        "component_interface_hints": ["src"],
                        "connector_semantic_hints": ["u", "y"],
                        "allowed_models": [
                            {"model_id": "c", "qualified_model_name": "LibB.C", "model_path": str(libb / "C.mo"), "scale_hint": "small"},
                            {"model_id": "d", "qualified_model_name": "LibB.D", "model_path": str(libb / "D.mo"), "scale_hint": "small"}
                        ]
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


class RunAgentModelicaUnknownLibraryEvidenceV1Tests(unittest.TestCase):
    def test_script_runs_end_to_end(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_unknown_library_evidence_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = _manifest(root)
            out_dir = root / "out"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_REPAIR_MEMORY": str(root / "missing_memory.json"),
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            decision = json.loads((out_dir / "decision_summary.json").read_text(encoding="utf-8"))
            retrieval = json.loads((out_dir / "retrieval_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(decision.get("status"), "PASS")
            self.assertGreaterEqual(float(retrieval.get("retrieval_coverage_pct") or 0.0), 50.0)


if __name__ == "__main__":
    unittest.main()

