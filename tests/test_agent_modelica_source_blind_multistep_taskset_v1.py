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
                "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=40, period=0.5);",
                "  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);",
                "  Modelica.Blocks.Sources.Constant c1(k=1);",
                "  Modelica.Blocks.Logical.Switch sw1;",
                "equation",
                "  connect(step1.y, sw1.u1);",
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
        "schema_version": "agent_modelica_source_blind_multistep_pack_manifest_v1",
        "libraries": [
            {
                "library_id": "liba",
                "package_name": "LibA",
                "source_library": "LibA",
                "license_provenance": "MIT",
                "domain": "controls",
                "source_type": "public_repo",
                "selection_reason": "a",
                "exposure_notes": "a",
                "allowed_models": [
                    {"model_id": "a", "qualified_model_name": "LibA.A", "model_path": str(root / "LibA/A.mo"), "selection_reason": "a", "exposure_notes": "a"},
                    {"model_id": "b", "qualified_model_name": "LibA.B", "model_path": str(root / "LibA/B.mo"), "selection_reason": "b", "exposure_notes": "b"},
                ],
            },
            {
                "library_id": "libb",
                "package_name": "LibB",
                "source_library": "LibB",
                "license_provenance": "MIT",
                "domain": "signals",
                "source_type": "research_artifact",
                "selection_reason": "c",
                "exposure_notes": "c",
                "allowed_models": [
                    {"model_id": "c", "qualified_model_name": "LibB.A", "model_path": str(root / "LibB/A.mo"), "selection_reason": "c", "exposure_notes": "c"},
                    {"model_id": "d", "qualified_model_name": "LibB.B", "model_path": str(root / "LibB/B.mo"), "selection_reason": "d", "exposure_notes": "d"},
                ],
            },
            {
                "library_id": "libc",
                "package_name": "LibC",
                "source_library": "LibC",
                "license_provenance": "MIT",
                "domain": "power",
                "source_type": "internal_mirror",
                "selection_reason": "e",
                "exposure_notes": "e",
                "allowed_models": [
                    {"model_id": "e", "qualified_model_name": "LibC.A", "model_path": str(root / "LibC/A.mo"), "selection_reason": "e", "exposure_notes": "e"},
                    {"model_id": "f", "qualified_model_name": "LibC.B", "model_path": str(root / "LibC/B.mo"), "selection_reason": "f", "exposure_notes": "f"},
                ],
            },
        ],
    }


class AgentModelicaSourceBlindMultistepTasksetV1Tests(unittest.TestCase):
    def test_builder_produces_multistep_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.agent_modelica_source_blind_multistep_taskset_v1", "--manifest", str(manifest), "--out-dir", str(out_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_tasks") or 0), 18)
            self.assertEqual(summary.get("counts_by_failure_type"), {
                "stability_then_behavior": 6,
                "behavior_then_robustness": 6,
                "switch_then_recovery": 6,
            })
            first = taskset["tasks"][0]
            self.assertEqual(first.get("expected_stage"), "simulate")
            self.assertIn(first.get("multi_step_family"), {"stability_then_behavior", "behavior_then_robustness", "switch_then_recovery"})
            self.assertEqual(first.get("pass_requirement"), "all_scenarios")
            self.assertEqual(len(first.get("expected_failure_sequence") or []), 2)
            self.assertEqual(int(first.get("scenario_count") or 0), 3)
            self.assertFalse(first.get("contract_pass_expected"))
            self.assertNotEqual(
                Path(first["source_model_path"]).read_text(encoding="utf-8"),
                Path(first["mutated_model_path"]).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
