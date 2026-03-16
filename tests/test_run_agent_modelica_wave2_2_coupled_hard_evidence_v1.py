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
    manifest = root / "manifest.json"
    libs = []
    for lib_id, band, source_type in (("liba", "less_likely_seen", "public_repo"), ("libb", "hard_unseen", "internal_mirror"), ("libc", "less_likely_seen", "research_artifact")):
        lib_dir = root / lib_id
        _write_model(lib_dir / "A.mo", "A")
        _write_model(lib_dir / "B.mo", "B")
        libs.append(
            {
                "library_id": lib_id,
                "package_name": lib_id.capitalize(),
                "source_library": lib_id.capitalize(),
                "license_provenance": "MIT",
                "domain": "controls",
                "seen_risk_band": band,
                "source_type": source_type,
                "selection_reason": lib_id,
                "exposure_notes": lib_id,
                "component_interface_hints": ["gain"],
                "connector_semantic_hints": ["u", "y"],
                "allowed_models": [
                    {"model_id": "a", "qualified_model_name": f"{lib_id.capitalize()}.A", "model_path": str(lib_dir / "A.mo"), "seen_risk_band": band, "source_type": source_type, "selection_reason": "a", "exposure_notes": "a"},
                    {"model_id": "b", "qualified_model_name": f"{lib_id.capitalize()}.B", "model_path": str(lib_dir / "B.mo"), "seen_risk_band": band, "source_type": source_type, "selection_reason": "b", "exposure_notes": "b"},
                ],
            }
        )
    manifest.write_text(json.dumps({"schema_version": "agent_modelica_wave2_2_coupled_hard_pack_manifest_v1", "libraries": libs}, indent=2), encoding="utf-8")
    return manifest


class RunAgentModelicaWave22CoupledHardEvidenceV1Tests(unittest.TestCase):
    def test_mock_chain_produces_wave2_2_decision(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_wave2_2_coupled_hard_evidence_v1.sh"
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
                    "GATEFORGE_AGENT_WAVE2_2_COUPLED_HARD_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_WAVE2_2_COUPLED_HARD_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_REPAIR_MEMORY_PATH": str(root / "missing_memory.json"),
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            decision = json.loads((out_dir / "decision_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(decision.get("status"), "NEEDS_REVIEW")
            self.assertTrue((out_dir / "wave2_2_baseline_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
