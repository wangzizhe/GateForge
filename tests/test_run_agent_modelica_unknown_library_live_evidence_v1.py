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
                            {"model_id": "b", "qualified_model_name": "LibA.B", "model_path": str(liba / "B.mo"), "scale_hint": "small"},
                        ],
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
                            {"model_id": "d", "qualified_model_name": "LibB.D", "model_path": str(libb / "D.mo"), "scale_hint": "small"},
                        ],
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


class RunAgentModelicaUnknownLibraryLiveEvidenceV1Tests(unittest.TestCase):
    def test_script_runs_with_mock_live_executor(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_unknown_library_live_evidence_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = _manifest(root)
            out_dir = root / "out"
            run_id = "live_mock01"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_LIVE_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUN_ID": run_id,
                    "GATEFORGE_AGENT_REPAIR_MEMORY_PATH": str(root / "missing_memory.json"),
                    "GATEFORGE_AGENT_LIVE_EXECUTOR_CMD": "python3 -m gateforge.agent_modelica_live_executor_mock_v0 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"rule\" --backend \"mock\"",
                    "GATEFORGE_AGENT_LIVE_OM_BACKEND": "mock",
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUN_BACKEND_PREFLIGHT": "0",
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            run_root = out_dir / "runs" / run_id
            decision = json.loads((run_root / "decision_summary.json").read_text(encoding="utf-8"))
            evidence = json.loads((run_root / "evidence_summary.json").read_text(encoding="utf-8"))
            latest_run = json.loads((out_dir / "latest_run.json").read_text(encoding="utf-8"))
            latest_summary = json.loads((out_dir / "latest_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(latest_run.get("run_id"), run_id)
            self.assertEqual(latest_summary.get("run_id"), run_id)
            self.assertTrue((run_root / "run_manifest.json").exists())
            self.assertTrue((run_root / "stages" / "challenge" / "stage_status.json").exists())
            self.assertEqual(decision.get("status"), "PASS")
            self.assertEqual(decision.get("decision"), "promote")
            success_by_library = evidence.get("success_by_library") if isinstance(evidence.get("success_by_library"), dict) else {}
            self.assertIn("liba", success_by_library)
            self.assertIn("retrieval_on_success_at_k_pct", success_by_library["liba"])

    def test_resume_script_completes_partial_run(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        run_script = repo_root / "scripts" / "run_agent_modelica_unknown_library_live_evidence_v1.sh"
        resume_script = repo_root / "scripts" / "resume_agent_modelica_unknown_library_live_run_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = _manifest(root)
            out_dir = root / "out"
            run_id = "resume01"
            base_env = {
                **os.environ,
                "GATEFORGE_AGENT_UNKNOWN_LIBRARY_MANIFEST": str(manifest),
                "GATEFORGE_AGENT_UNKNOWN_LIBRARY_LIVE_EVIDENCE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUN_ID": run_id,
                "GATEFORGE_AGENT_REPAIR_MEMORY_PATH": str(root / "missing_memory.json"),
                "GATEFORGE_AGENT_LIVE_EXECUTOR_CMD": "python3 -m gateforge.agent_modelica_live_executor_mock_v0 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"rule\" --backend \"mock\"",
                "GATEFORGE_AGENT_LIVE_OM_BACKEND": "mock",
                "GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUN_BACKEND_PREFLIGHT": "0",
            }
            proc_a = subprocess.run(
                ["bash", str(run_script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={**base_env, "GATEFORGE_AGENT_UNKNOWN_LIBRARY_STOP_AFTER_STAGE": "baseline_off_live"},
                timeout=900,
            )
            self.assertEqual(proc_a.returncode, 0, msg=proc_a.stderr or proc_a.stdout)
            run_root = out_dir / "runs" / run_id
            self.assertTrue((run_root / "stages" / "baseline_off_live" / "stage_status.json").exists())
            self.assertFalse((run_root / "decision_summary.json").exists())
            self.assertFalse((out_dir / "latest_run.json").exists())

            proc_b = subprocess.run(
                ["bash", str(resume_script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **base_env,
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_RESUME_RUN_ID": run_id,
                },
                timeout=900,
            )
            self.assertEqual(proc_b.returncode, 0, msg=proc_b.stderr or proc_b.stdout)
            decision = json.loads((run_root / "decision_summary.json").read_text(encoding="utf-8"))
            latest_run = json.loads((out_dir / "latest_run.json").read_text(encoding="utf-8"))
            self.assertEqual(decision.get("status"), "PASS")
            self.assertEqual(latest_run.get("run_id"), run_id)
            self.assertTrue((run_root / "stages" / "retrieval_on_live" / "stage_status.json").exists())
