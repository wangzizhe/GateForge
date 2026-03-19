import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_behavioral_robustness_taskset_v1 import _mutate_behavioral_robustness_model


def _write_model(path: Path, model_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"model {model_name}",
                "  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);",
                "  Modelica.Blocks.Continuous.TransferFunction tf1(b={1}, a={1,1});",
                "  Modelica.Blocks.Logical.Switch sw1;",
                "equation",
                "  connect(step1.y, tf1.u);",
                "  connect(tf1.y, sw1.u1);",
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
        "schema_version": "agent_modelica_behavioral_robustness_pack_manifest_v1",
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


class AgentModelicaBehavioralRobustnessTasksetV1Tests(unittest.TestCase):
    def test_mutations_touch_real_parameters(self) -> None:
        source_text = "\n".join(
            [
                "model A",
                "  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);",
                "  Modelica.Blocks.Continuous.TransferFunction tf1(b={1}, a={1,1});",
                "  Modelica.Blocks.Logical.Switch sw1;",
                "end A;",
                "",
            ]
        )
        self.assertIn("k=1.18", _mutate_behavioral_robustness_model(source_text.replace("b={1}", "k=1"), "param_perturbation_robustness_violation"))
        self.assertIn("startTime=0.45", _mutate_behavioral_robustness_model(source_text, "initial_condition_robustness_violation"))
        self.assertIn("startTime=0.6", _mutate_behavioral_robustness_model(source_text, "scenario_switch_robustness_violation"))

    def test_switch_a_mutations_touch_width_and_period(self) -> None:
        source_text = "\n".join(
            [
                "model SwitchA",
                "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=40, period=0.5);",
                "  Modelica.Blocks.Sources.Constant c1(k=1);",
                "  Modelica.Blocks.Sources.Constant c0(k=0);",
                "  Modelica.Blocks.Logical.Switch sw1;",
                "end SwitchA;",
                "",
            ]
        )
        mutated = _mutate_behavioral_robustness_model(source_text, "initial_condition_robustness_violation")
        self.assertIn("width=18", mutated)
        self.assertIn("period=0.28", mutated)

    def test_builder_produces_robustness_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.agent_modelica_behavioral_robustness_taskset_v1", "--manifest", str(manifest), "--out-dir", str(out_dir)],
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
                "param_perturbation_robustness_violation": 6,
                "initial_condition_robustness_violation": 6,
                "scenario_switch_robustness_violation": 6,
            })
            first = taskset["tasks"][0]
            self.assertEqual(first.get("expected_stage"), "simulate")
            self.assertIn(first.get("robustness_family"), {"param_perturbation", "initial_condition", "scenario_switch"})
            self.assertEqual(first.get("pass_requirement"), "all_scenarios")
            self.assertEqual(int(first.get("scenario_count") or 0), 3)
            self.assertEqual(len(first.get("scenario_matrix") or []), 3)
            self.assertFalse(first.get("contract_pass_expected"))
            self.assertTrue(isinstance(summary.get("scenario_count_distribution"), dict))
            source_text = Path(first["source_model_path"]).read_text(encoding="utf-8")
            mutated_text = Path(first["mutated_model_path"]).read_text(encoding="utf-8")
            self.assertNotEqual(source_text, mutated_text)


if __name__ == "__main__":
    unittest.main()
