import json
import subprocess
import sys
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


def _manifest_payload(root: Path) -> dict:
    for lib in ("LibA", "LibB", "LibC"):
        for name in ("A", "B"):
            _write_model(root / lib / f"{name}.mo", name)
    return {
        "schema_version": "agent_modelica_wave2_1_harder_dynamics_pack_manifest_v1",
        "libraries": [
            {
                "library_id": "liba",
                "package_name": "LibA",
                "source_library": "LibA",
                "license_provenance": "MIT",
                "domain": "controls",
                "seen_risk_band": "less_likely_seen",
                "source_type": "public_repo",
                "selection_reason": "a",
                "exposure_notes": "a",
                "component_interface_hints": ["gain"],
                "connector_semantic_hints": ["u", "y"],
                "allowed_models": [
                    {"model_id": "a", "qualified_model_name": "LibA.A", "model_path": str(root / "LibA/A.mo"), "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "a", "exposure_notes": "a"},
                    {"model_id": "b", "qualified_model_name": "LibA.B", "model_path": str(root / "LibA/B.mo"), "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "b", "exposure_notes": "b"},
                ],
            },
            {
                "library_id": "libb",
                "package_name": "LibB",
                "source_library": "LibB",
                "license_provenance": "MIT",
                "domain": "signals",
                "seen_risk_band": "hard_unseen",
                "source_type": "internal_mirror",
                "selection_reason": "c",
                "exposure_notes": "c",
                "component_interface_hints": ["src"],
                "connector_semantic_hints": ["u", "y"],
                "allowed_models": [
                    {"model_id": "c", "qualified_model_name": "LibB.A", "model_path": str(root / "LibB/A.mo"), "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "c", "exposure_notes": "c"},
                    {"model_id": "d", "qualified_model_name": "LibB.B", "model_path": str(root / "LibB/B.mo"), "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "d", "exposure_notes": "d"},
                ],
            },
            {
                "library_id": "libc",
                "package_name": "LibC",
                "source_library": "LibC",
                "license_provenance": "MIT",
                "domain": "power",
                "seen_risk_band": "less_likely_seen",
                "source_type": "research_artifact",
                "selection_reason": "e",
                "exposure_notes": "e",
                "component_interface_hints": ["const"],
                "connector_semantic_hints": ["u", "y"],
                "allowed_models": [
                    {"model_id": "e", "qualified_model_name": "LibC.A", "model_path": str(root / "LibC/A.mo"), "seen_risk_band": "less_likely_seen", "source_type": "research_artifact", "selection_reason": "e", "exposure_notes": "e"},
                    {"model_id": "f", "qualified_model_name": "LibC.B", "model_path": str(root / "LibC/B.mo"), "seen_risk_band": "less_likely_seen", "source_type": "research_artifact", "selection_reason": "f", "exposure_notes": "f"},
                ],
            },
        ],
    }


class AgentModelicaWave21HarderDynamicsTasksetV1Tests(unittest.TestCase):
    def test_builder_produces_dynamic_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.agent_modelica_wave2_1_harder_dynamics_taskset_v1", "--manifest", str(manifest), "--out-dir", str(out_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_tasks") or 0), 18)
            self.assertEqual(summary.get("counts_by_failure_type"), {"solver_sensitive_simulate_failure": 6, "event_logic_error": 6, "semantic_drift_after_compile_pass": 6})
            first = taskset["tasks"][0]
            self.assertIn(first.get("failure_type"), {"solver_sensitive_simulate_failure", "event_logic_error", "semantic_drift_after_compile_pass"})
            self.assertTrue(first.get("dynamic_error_family"))
            self.assertTrue(first.get("diagnostic_expectation"))


if __name__ == "__main__":
    unittest.main()
