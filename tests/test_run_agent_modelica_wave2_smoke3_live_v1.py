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
    for lib_id, band, source_type in (("buildings", "less_likely_seen", "public_repo"), ("ibpsa", "hard_unseen", "internal_mirror"), ("transform", "less_likely_seen", "research_artifact")):
        lib_dir = root / lib_id
        for name in ("loads", "simplebattery_test"):
            _write_model(lib_dir / f"{name}.mo", name)
        allowed = []
        if lib_id == "transform":
            allowed = [
                {"model_id": "simplebattery_test", "qualified_model_name": "Transform.SimpleBattery_Test", "model_path": str(lib_dir / "simplebattery_test.mo"), "seen_risk_band": band, "source_type": source_type, "selection_reason": "a", "exposure_notes": "a"},
                {"model_id": "loads", "qualified_model_name": "Transform.Loads", "model_path": str(lib_dir / "loads.mo"), "seen_risk_band": band, "source_type": source_type, "selection_reason": "b", "exposure_notes": "b"},
            ]
        else:
            allowed = [
                {"model_id": "loads", "qualified_model_name": f"{lib_id.capitalize()}.Loads", "model_path": str(lib_dir / "loads.mo"), "seen_risk_band": band, "source_type": source_type, "selection_reason": "a", "exposure_notes": "a"},
                {"model_id": "acsimplegrid", "qualified_model_name": f"{lib_id.capitalize()}.ACSimpleGrid", "model_path": str(lib_dir / "simplebattery_test.mo"), "seen_risk_band": band, "source_type": source_type, "selection_reason": "b", "exposure_notes": "b"},
            ]
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
                "allowed_models": allowed,
            }
        )
    manifest.write_text(json.dumps({"schema_version": "agent_modelica_wave2_realism_pack_manifest_v1", "libraries": libs}, indent=2), encoding="utf-8")
    return manifest


class RunAgentModelicaWave2Smoke3LiveV1Tests(unittest.TestCase):
    def test_script_runs_with_mock_executor(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_wave2_smoke3_live_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = _manifest(root)
            out_dir = root / "out"
            run_id = "wave2_smoke3_mock01"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_WAVE2_REALISM_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_WAVE2_SMOKE3_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_WAVE2_SMOKE3_RUN_ID": run_id,
                    "GATEFORGE_AGENT_LIVE_EXECUTOR_CMD": "python3 -m gateforge.agent_modelica_live_executor_mock_v0 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"rule\" --backend \"mock\"",
                    "GATEFORGE_AGENT_LIVE_OM_BACKEND": "mock",
                    "GATEFORGE_AGENT_WAVE2_REALISM_RUN_BACKEND_PREFLIGHT": "0",
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            run_root = out_dir / "runs" / run_id
            final = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            smoke = json.loads((run_root / "smoke_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(final.get("status"), "PASS")
            self.assertEqual(smoke.get("total_tasks"), 3)


if __name__ == "__main__":
    unittest.main()
