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
                "allowed_models": [
                    {"model_id": "a", "qualified_model_name": f"{lib_id.capitalize()}.A", "model_path": str(lib_dir / "A.mo"), "seen_risk_band": band, "source_type": source_type, "selection_reason": "a", "exposure_notes": "a"},
                    {"model_id": "b", "qualified_model_name": f"{lib_id.capitalize()}.B", "model_path": str(lib_dir / "B.mo"), "seen_risk_band": band, "source_type": source_type, "selection_reason": "b", "exposure_notes": "b"},
                ],
            }
        )
    manifest.write_text(json.dumps({"schema_version": "agent_modelica_multi_round_failure_pack_manifest_v1", "libraries": libs}, indent=2), encoding="utf-8")
    return manifest


class RunAgentModelicaMultiRoundFailureEvidenceV1Tests(unittest.TestCase):
    def test_mock_chain_produces_multi_round_decision(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_multi_round_failure_evidence_v1.sh"
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
                    "GATEFORGE_AGENT_MULTI_ROUND_FAILURE_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_MULTI_ROUND_FAILURE_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_REPAIR_MEMORY_PATH": str(root / "missing_memory.json"),
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            decision = json.loads((out_dir / "decision_summary.json").read_text(encoding="utf-8"))
            self.assertIn(decision.get("status"), {"NEEDS_REVIEW", "PASS"})
            self.assertTrue((out_dir / "multi_round_baseline_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
