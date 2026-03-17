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
                "  Modelica.Blocks.Sources.Ramp load_inputs(height=5000, duration=0.5, startTime=0.25);",
                "  Modelica.Blocks.Sources.Constant ph_1(k=1);",
                "  Modelica.Blocks.Sources.Constant ph_23(k=0);",
                "  Modelica.Blocks.Sources.Constant cons(k=10);",
                "  Modelica.Blocks.Sources.Ramp ramp(height=-1, duration=1, startTime=0.2);",
                "  Modelica.Blocks.Sources.BooleanPulse booleanPulse(width=50, period=0.2);",
                "  Modelica.Blocks.Sources.SampleTrigger sampleTrigger(period=0.2);",
                "  Modelica.Blocks.Sources.Trapezoid trapezoid(amplitude=1e6, width=1000, period=4000, startTime=1000);",
                "  Modelica.Blocks.Continuous.Integrator intWitRes1(k=0.5);",
                "  Modelica.Blocks.Continuous.Integrator intWitRes2(k=0.5);",
                "  Dummy load;",
                "  Dummy network;",
                "  Dummy loaR;",
                "  Dummy battery;",
                "  Dummy boundary;",
                "equation",
                "  connect(load.terminal, network.terminal[2]);",
                "  connect(load_inputs.y, load.Pow1);",
                "  connect(load_inputs.y, load.Pow2);",
                "  connect(ph_23.y, loaR.Pow2);",
                "  connect(ph_23.y, loaR.Pow3);",
                "  connect(cons.y, intWitRes1.u);",
                "  connect(cons.y, intWitRes2.u);",
                "  connect(booleanPulse.y, intWitRes2.trigger);",
                "  connect(sampleTrigger.y, intWitRes2.trigger);",
                "  connect(trapezoid.y, battery.W_setpoint);",
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
        "schema_version": "agent_modelica_multi_round_failure_pack_manifest_v1",
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
                "allowed_models": [
                    {"model_id": "e", "qualified_model_name": "LibC.A", "model_path": str(root / "LibC/A.mo"), "seen_risk_band": "less_likely_seen", "source_type": "research_artifact", "selection_reason": "e", "exposure_notes": "e"},
                    {"model_id": "f", "qualified_model_name": "LibC.B", "model_path": str(root / "LibC/B.mo"), "seen_risk_band": "less_likely_seen", "source_type": "research_artifact", "selection_reason": "f", "exposure_notes": "f"},
                ],
            },
        ],
    }


class AgentModelicaMultiRoundFailureTasksetV1Tests(unittest.TestCase):
    def test_builder_produces_multi_round_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.agent_modelica_multi_round_failure_taskset_v1", "--manifest", str(manifest), "--out-dir", str(out_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_tasks") or 0), 18)
            self.assertEqual(summary.get("counts_by_failure_type"), {"cascading_structural_failure": 6, "coupled_conflict_failure": 6, "false_friend_patch_trap": 6})
            first = taskset["tasks"][0]
            self.assertGreaterEqual(int(first.get("expected_rounds_min") or 0), 2)
            self.assertGreaterEqual(int(first.get("source_rewrite_count") or 0), 4)
            self.assertGreaterEqual(int(first.get("mutation_span_count") or 0), 6)
            self.assertIn(first.get("multi_round_family"), {"cascade", "coupled_conflict", "false_friend"})
            self.assertTrue(isinstance(first.get("expected_stage_sequence"), list))


if __name__ == "__main__":
    unittest.main()
