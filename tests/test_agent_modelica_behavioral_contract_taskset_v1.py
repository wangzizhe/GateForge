import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_behavioral_contract_taskset_v1 import (
    _mutate_behavioral_model,
    _normalize_behavioral_source_model_text,
)


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
        "schema_version": "agent_modelica_behavioral_contract_pack_manifest_v1",
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


class AgentModelicaBehavioralContractTasksetV1Tests(unittest.TestCase):
    def test_normalize_switch_b_source_model_text(self) -> None:
        source_text = "\n".join(
            [
                "model SwitchB",
                "  Modelica.Blocks.Sources.Sine sine1(freqHz=1);",
                "end SwitchB;",
                "",
            ]
        )
        normalized = _normalize_behavioral_source_model_text(source_text)
        self.assertIn("Sine sine1(f=1)", normalized)
        self.assertNotIn("freqHz=", normalized)

    def test_switch_b_mutations_touch_real_source_parameters(self) -> None:
        source_text = "\n".join(
            [
                "model SwitchB",
                "  Modelica.Blocks.Sources.BooleanStep step1(startTime=0.3);",
                "  Modelica.Blocks.Sources.Sine sine1(freqHz=1);",
                "  Modelica.Blocks.Sources.Constant ref1(k=0.5);",
                "  Modelica.Blocks.Logical.Switch sw1;",
                "equation",
                "  connect(sine1.y, sw1.u1);",
                "  connect(step1.y, sw1.u2);",
                "  connect(ref1.y, sw1.u3);",
                "end SwitchB;",
                "",
            ]
        )
        steady = _mutate_behavioral_model(source_text, "steady_state_target_violation")
        transient = _mutate_behavioral_model(source_text, "transient_response_contract_violation")
        mode = _mutate_behavioral_model(source_text, "mode_transition_contract_violation")
        self.assertIn("k=0.82", steady)
        self.assertIn("freqHz=2.5", transient)
        self.assertIn("k=1.25", transient)
        self.assertIn("startTime=0.6", mode)
        self.assertIn("k=0.4", mode)

    def test_builder_produces_behavioral_contract_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.agent_modelica_behavioral_contract_taskset_v1", "--manifest", str(manifest), "--out-dir", str(out_dir)],
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
                "steady_state_target_violation": 6,
                "transient_response_contract_violation": 6,
                "mode_transition_contract_violation": 6,
            })
            first = taskset["tasks"][0]
            self.assertEqual(first.get("expected_stage"), "simulate")
            self.assertIn(first.get("contract_family"), {"steady_state", "transient_response", "mode_transition"})
            self.assertTrue(first.get("compile_pass_expected"))
            self.assertTrue(first.get("simulate_pass_expected"))
            self.assertFalse(first.get("contract_pass_expected"))
            self.assertTrue(isinstance(first.get("contract_metric_set"), list))
            self.assertTrue(isinstance(first.get("expected_contract_failures"), list))
            self.assertGreaterEqual(int(first.get("expected_rounds_min") or 0), 2)
            self.assertTrue(isinstance(summary.get("contract_metric_coverage"), dict))
            source_text = Path(first["source_model_path"]).read_text(encoding="utf-8")
            mutated_text = Path(first["mutated_model_path"]).read_text(encoding="utf-8")
            self.assertNotEqual(source_text, mutated_text)
            self.assertIn("gateforge_behavioral_contract_violation", mutated_text)


if __name__ == "__main__":
    unittest.main()
