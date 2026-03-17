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
                "  Modelica.Blocks.Sources.Step step(height=1, startTime=0.2);",
                "  Modelica.Blocks.Sources.BooleanPulse pulse(width=40, period=0.5, startTime=0.1);",
                "  Modelica.Blocks.Sources.Sine sine(freqHz=1);",
                "  Modelica.Blocks.Continuous.TransferFunction tf(b={1}, a={0.2, 1});",
                "  Modelica.Blocks.Continuous.FirstOrder lag(k=1, T=0.2);",
                "  Modelica.Blocks.Math.Gain gain(k=0.5);",
                "equation",
                "  connect(step.y, tf.u);",
                "  connect(tf.y, lag.u);",
                "  connect(lag.y, gain.u);",
                f"end {model_name};",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _manifest(root: Path) -> Path:
    manifest = root / "manifest.json"
    libraries = []
    for lib_id, source_type in (
        ("liba", "public_repo"),
        ("libb", "internal_mirror"),
        ("libc", "research_artifact"),
    ):
        lib_dir = root / lib_id
        _write_model(lib_dir / "A.mo", "A")
        _write_model(lib_dir / "B.mo", "B")
        libraries.append(
            {
                "library_id": lib_id,
                "package_name": lib_id.capitalize(),
                "source_library": lib_id.capitalize(),
                "license_provenance": "MIT",
                "domain": "controls",
                "source_type": source_type,
                "selection_reason": lib_id,
                "exposure_notes": lib_id,
                "allowed_models": [
                    {
                        "model_id": "a",
                        "qualified_model_name": f"{lib_id.capitalize()}.A",
                        "model_path": str(lib_dir / "A.mo"),
                        "selection_reason": "a",
                        "exposure_notes": "a",
                        "scale_hint": "small",
                        "preferred_failure_types": [
                            "steady_state_target_violation",
                            "transient_response_contract_violation",
                            "mode_transition_contract_violation",
                        ],
                    },
                    {
                        "model_id": "b",
                        "qualified_model_name": f"{lib_id.capitalize()}.B",
                        "model_path": str(lib_dir / "B.mo"),
                        "selection_reason": "b",
                        "exposure_notes": "b",
                        "scale_hint": "small",
                        "preferred_failure_types": [
                            "steady_state_target_violation",
                            "transient_response_contract_violation",
                            "mode_transition_contract_violation",
                        ],
                    },
                ],
            }
        )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "agent_modelica_behavioral_contract_pack_manifest_v1",
                "libraries": libraries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


class RunAgentModelicaBehavioralContractEvidenceV1Tests(unittest.TestCase):
    def test_mock_chain_produces_behavioral_decision(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_behavioral_contract_evidence_v1.sh"
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
                    "GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_EVIDENCE_OUT_DIR": str(out_dir),
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            decision = json.loads((out_dir / "decision_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(decision.get("primary_reason"), "retrieval_hold_the_floor")
            self.assertEqual(decision.get("decision"), "promote")
            self.assertTrue((out_dir / "behavioral_contract_baseline_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
