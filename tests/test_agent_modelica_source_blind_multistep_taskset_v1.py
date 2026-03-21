import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_source_blind_multistep_taskset_v1 import _mutate_source_blind_multistep_model


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


def _realistic_manifest_payload(root: Path) -> dict:
    realistic = [
        ("behaviorliba", "BehaviorLibA", "plant_a", "PlantA"),
        ("behaviorliba", "BehaviorLibA", "plant_b", "PlantB"),
        ("behaviorlibb", "BehaviorLibB", "switch_a", "SwitchA"),
        ("behaviorlibb", "BehaviorLibB", "switch_b", "SwitchB"),
        ("behaviorlibc", "BehaviorLibC", "hybrid_a", "HybridA"),
        ("behaviorlibc", "BehaviorLibC", "hybrid_b", "HybridB"),
    ]
    libraries: dict[str, dict] = {}
    for library_id, package_name, model_id, model_name in realistic:
        package_dir = root / package_name
        _write_model(package_dir / f"{model_name}.mo", model_name)
        row = libraries.setdefault(
            library_id,
            {
                "library_id": library_id,
                "package_name": package_name,
                "source_library": package_name,
                "license_provenance": "MIT",
                "domain": "controls",
                "source_type": "public_repo",
                "selection_reason": package_name,
                "exposure_notes": package_name,
                "allowed_models": [],
            },
        )
        row["allowed_models"].append(
            {
                "model_id": model_id,
                "qualified_model_name": f"{package_name}.{model_name}",
                "model_path": str(package_dir / f"{model_name}.mo"),
                "selection_reason": model_name,
                "exposure_notes": model_name,
            }
        )
    return {
        "schema_version": "agent_modelica_source_blind_multistep_pack_manifest_v1",
        "libraries": list(libraries.values()),
    }


class AgentModelicaSourceBlindMultistepTasksetV1Tests(unittest.TestCase):
    def test_mutate_source_blind_multistep_model_adds_switcha_stage2_behavior_layer(self) -> None:
        source = (
            "model SwitchA\n"
            "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=40, period=0.5);\n"
            "  Modelica.Blocks.Sources.Constant c1(k=1);\n"
            "end SwitchA;\n"
        )
        mutated = _mutate_source_blind_multistep_model(source, "stability_then_behavior")
        self.assertIn("width=62", mutated)
        self.assertIn("period=0.85", mutated)
        self.assertIn("k=1.18", mutated)

    def test_mutate_source_blind_multistep_model_adds_plantb_recovery_second_layer(self) -> None:
        source = (
            "model PlantB\n"
            "  Modelica.Blocks.Sources.Ramp ramp1(height=1, duration=0.5, startTime=0.2);\n"
            "end PlantB;\n"
        )
        mutated = _mutate_source_blind_multistep_model(source, "switch_then_recovery")
        self.assertIn("duration=1.1", mutated)
        self.assertIn("startTime=0.6", mutated)

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
            self.assertEqual(first.get("realism_version"), "v3")
            self.assertTrue(first.get("stage_2_branches"))
            self.assertTrue(first.get("preferred_stage_2_branch"))
            self.assertTrue(first.get("trap_stage_2_branch"))
            self.assertEqual(first.get("pass_requirement"), "all_scenarios")
            self.assertEqual(len(first.get("expected_failure_sequence") or []), 2)
            self.assertEqual(int(first.get("scenario_count") or 0), 3)
            self.assertFalse(first.get("contract_pass_expected"))
            self.assertNotEqual(
                Path(first["source_model_path"]).read_text(encoding="utf-8"),
                Path(first["mutated_model_path"]).read_text(encoding="utf-8"),
            )

    def test_builder_v4_produces_llm_forcing_subset(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_realistic_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_source_blind_multistep_taskset_v1",
                    "--manifest",
                    str(manifest),
                    "--out-dir",
                    str(out_dir),
                    "--realism-version",
                    "v4",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("realism_version"), "v4")
            self.assertEqual(int(summary.get("total_tasks") or 0), 6)
            first = taskset["tasks"][0]
            self.assertEqual(first.get("realism_version"), "v4")
            self.assertTrue(bool(first.get("llm_forcing")))
            self.assertTrue(str(first.get("llm_forcing_profile") or "").strip())
            self.assertTrue(str(first.get("llm_trigger_reason") or "").strip())
            mutated = Path(first["mutated_model_path"]).read_text(encoding="utf-8")
            self.assertIn("gateforge_source_blind_multistep_llm_forcing:1", mutated)
            self.assertIn("gateforge_source_blind_multistep_realism_version:v4", mutated)

    def test_builder_v5_produces_harder_llm_forcing_subset(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_realistic_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_source_blind_multistep_taskset_v1",
                    "--manifest",
                    str(manifest),
                    "--out-dir",
                    str(out_dir),
                    "--realism-version",
                    "v5",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("realism_version"), "v5")
            self.assertEqual(int(summary.get("total_tasks") or 0), 6)
            first = taskset["tasks"][0]
            self.assertEqual(first.get("realism_version"), "v5")
            self.assertTrue(bool(first.get("llm_forcing")))
            self.assertTrue(str(first.get("llm_forcing_profile") or "").strip())
            self.assertTrue(str(first.get("llm_trigger_reason") or "").strip())
            mutated = Path(first["mutated_model_path"]).read_text(encoding="utf-8")
            self.assertIn("gateforge_source_blind_multistep_llm_forcing:1", mutated)
            self.assertIn("gateforge_source_blind_multistep_realism_version:v5", mutated)


if __name__ == "__main__":
    unittest.main()
