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
    manifest.write_text(json.dumps({"schema_version": "agent_modelica_wave2_realism_pack_manifest_v1", "libraries": libs}, indent=2), encoding="utf-8")
    return manifest


class RunAgentModelicaWave2RealismLiveEvidenceV1Tests(unittest.TestCase):
    def test_live_wrapper_runs_with_mock_executor(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_wave2_realism_live_evidence_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = _manifest(root)
            out_dir = root / "out"
            run_id = "wave2_live_mock01"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_WAVE2_REALISM_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_WAVE2_REALISM_LIVE_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_WAVE2_REALISM_RUN_ID": run_id,
                    "GATEFORGE_AGENT_REPAIR_MEMORY_PATH": str(root / "missing_memory.json"),
                    "GATEFORGE_AGENT_LIVE_EXECUTOR_CMD": "python3 -m gateforge.agent_modelica_live_executor_mock_v0 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"rule\" --backend \"mock\"",
                    "GATEFORGE_AGENT_LIVE_OM_BACKEND": "mock",
                    "GATEFORGE_AGENT_WAVE2_REALISM_RUN_BACKEND_PREFLIGHT": "0",
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            run_root = out_dir / "runs" / run_id
            final = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            decision = json.loads((run_root / "decision_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(final.get("status"), "PASS")
            self.assertEqual(decision.get("status"), "PASS")
            self.assertTrue((run_root / "wave2_baseline_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
