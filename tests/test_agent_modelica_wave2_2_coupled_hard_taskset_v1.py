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
        "schema_version": "agent_modelica_wave2_2_coupled_hard_pack_manifest_v1",
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


class AgentModelicaWave22CoupledHardTasksetV1Tests(unittest.TestCase):
    def test_builder_produces_coupled_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.agent_modelica_wave2_2_coupled_hard_taskset_v1", "--manifest", str(manifest), "--out-dir", str(out_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_tasks") or 0), 18)
            self.assertEqual(int(summary.get("rejected_candidate_count") or 0), 0)
            self.assertEqual(
                summary.get("counts_by_failure_type"),
                {
                    "cross_component_parameter_coupling_error": 6,
                    "control_loop_sign_semantic_drift": 6,
                    "mode_switch_guard_logic_error": 6,
                },
            )
            first = taskset["tasks"][0]
            self.assertIn(first.get("failure_type"), {"cross_component_parameter_coupling_error", "control_loop_sign_semantic_drift", "mode_switch_guard_logic_error"})
            self.assertIn(first.get("coupling_span"), {"cross_component", "control_loop"})
            self.assertEqual(first.get("repair_triviality_risk"), "low")
            self.assertGreaterEqual(int(first.get("mutation_span_count") or 0), 3)
            self.assertTrue(bool(first.get("delayed_failure_signal")))
            self.assertTrue(bool(first.get("compile_pass_expected")))
            self.assertTrue(bool(first.get("simulate_phase_required")))
            self.assertTrue(bool(first.get("trivial_restore_guard")))
            self.assertGreaterEqual(int(first.get("source_dependency_count") or 0), 2)
            self.assertTrue(bool(first.get("uses_existing_equation_context")))
            self.assertGreater(float(first.get("failure_signal_delay_sec") or 0.0), 0.1)

            drift_task = next(
                row for row in taskset["tasks"] if row.get("failure_type") == "control_loop_sign_semantic_drift"
            )
            drift_text = Path(drift_task["mutated_model_path"]).read_text(encoding="utf-8")
            self.assertIn("__gf_loop_trigger_time_", drift_text)
            self.assertIn("time < __gf_loop_trigger_time_", drift_text)
            self.assertIn("__gf_loop_state_", drift_text)


if __name__ == "__main__":
    unittest.main()
