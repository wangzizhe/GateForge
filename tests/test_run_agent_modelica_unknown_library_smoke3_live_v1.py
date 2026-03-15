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
    libc = root / "LibC"
    for path in (liba / "A.mo", liba / "A2.mo", libb / "B.mo", libb / "B2.mo", libc / "C.mo", libc / "C2.mo"):
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
                        "allowed_models": [
                            {"model_id": "a", "qualified_model_name": "LibA.A", "model_path": str(liba / "A.mo"), "scale_hint": "small"},
                            {"model_id": "a2", "qualified_model_name": "LibA.A2", "model_path": str(liba / "A2.mo"), "scale_hint": "small"},
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
                        "allowed_models": [
                            {"model_id": "b", "qualified_model_name": "LibB.B", "model_path": str(libb / "B.mo"), "scale_hint": "small"},
                            {"model_id": "b2", "qualified_model_name": "LibB.B2", "model_path": str(libb / "B2.mo"), "scale_hint": "small"},
                        ],
                    },
                    {
                        "library_id": "libc",
                        "package_name": "LibC",
                        "source_library": "LibC",
                        "license_provenance": "MIT",
                        "local_path": str(libc),
                        "accepted_source_path": str(libc),
                        "domain": "thermal",
                        "allowed_models": [
                            {"model_id": "c", "qualified_model_name": "LibC.C", "model_path": str(libc / "C.mo"), "scale_hint": "small"},
                            {"model_id": "c2", "qualified_model_name": "LibC.C2", "model_path": str(libc / "C2.mo"), "scale_hint": "small"},
                        ],
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


class RunAgentModelicaUnknownLibrarySmoke3LiveV1Tests(unittest.TestCase):
    def test_script_runs_three_task_baseline_only_with_mock_executor(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_unknown_library_smoke3_live_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = _manifest(root)
            out_dir = root / "out"
            run_id = "smoke3_mock01"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_SMOKE3_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_SMOKE3_RUN_ID": run_id,
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_SMOKE_TASK_IDS": ",".join(
                        [
                            "unknownlib_liba_a_connector_mismatch",
                            "unknownlib_libb_b_connector_mismatch",
                            "unknownlib_libc_c_connector_mismatch",
                        ]
                    ),
                    "GATEFORGE_AGENT_LIVE_EXECUTOR_CMD": "python3 -m gateforge.agent_modelica_live_executor_mock_v0 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"rule\" --backend \"mock\"",
                    "GATEFORGE_AGENT_LIVE_OM_BACKEND": "mock",
                    "GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUN_BACKEND_PREFLIGHT": "0",
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            run_root = out_dir / "runs" / run_id
            smoke_taskset = json.loads((run_root / "smoke_taskset" / "taskset_frozen.json").read_text(encoding="utf-8"))
            baseline = json.loads((run_root / "baseline_off_live" / "summary.json").read_text(encoding="utf-8"))
            smoke_summary = json.loads((run_root / "smoke_summary.json").read_text(encoding="utf-8"))
            latest_summary = json.loads((out_dir / "latest_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(len(smoke_taskset.get("tasks") or []), 3)
            self.assertEqual(int(baseline.get("total_tasks") or 0), 3)
            self.assertEqual(smoke_summary.get("status"), "PASS")
            self.assertEqual(latest_summary.get("run_id"), run_id)
            self.assertFalse((run_root / "retrieval_on_live" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
