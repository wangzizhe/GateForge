from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_staged_residual_pack_v0_22_4 import (
    build_staged_residual_candidates,
    mutate_measurement_interface_then_constraint_residual,
    mutate_staged_parameter_and_phantom_residual,
    mutate_structural_deficit_with_residual_symbol_exposure,
    run_staged_residual_pack,
    summarize_staged_residual_pack,
)


SOURCE_TEXT = """model A
  // gateforge_validation_targets: VS1.v
  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10.0);
  Modelica.Electrical.Analog.Basic.Resistor R1(R=100.0);
  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.01);
  Modelica.Electrical.Analog.Sensors.VoltageSensor VS1;
  Modelica.Electrical.Analog.Basic.Ground G;
equation
  connect(V1.p, R1.p);
  connect(R1.n, C1.p);
  connect(C1.n, V1.n);
  connect(V1.n, G.p);
  connect(VS1.p, C1.p);
  connect(VS1.n, G.p);
end A;
"""


def _source_row(path: Path) -> dict:
    return {
        "source_model_path": str(path),
        "source_model_name": "A",
        "source_viability_status": "historically_verified_clean_source",
        "source_evidence_artifact": "cases.jsonl",
        "source_evidence_case_id": "case_a",
    }


def _fake_check(_model_text: str, _model_name: str) -> tuple[bool, str]:
    return False, "Error: Variable stagedResidualSymbol not found in scope A"


class StagedResidualPackV0224Tests(unittest.TestCase):
    def test_parameter_and_phantom_residual_contains_two_stages(self) -> None:
        attempt = mutate_staged_parameter_and_phantom_residual(SOURCE_TEXT)

        self.assertTrue(attempt.changed)
        self.assertIn("branchResistance[1]", attempt.target_text)
        self.assertIn("stagedLossPhantom", attempt.target_text)
        self.assertGreaterEqual(len(attempt.stage_residuals), 2)

    def test_measurement_interface_then_constraint_residual_contains_assertion_layer(self) -> None:
        attempt = mutate_measurement_interface_then_constraint_residual(SOURCE_TEXT)

        self.assertTrue(attempt.changed)
        self.assertIn("PowerSensor VS1", attempt.target_text)
        self.assertIn("assert(stagedPower < -1.0", attempt.target_text)
        self.assertGreaterEqual(len(attempt.stage_residuals), 2)

    def test_structural_deficit_with_symbol_exposure_removes_connection_and_adds_symbol(self) -> None:
        attempt = mutate_structural_deficit_with_residual_symbol_exposure(SOURCE_TEXT)

        self.assertTrue(attempt.changed)
        self.assertIn("staged residual removed one connection", attempt.target_text)
        self.assertIn("stagedResidualSymbol", attempt.target_text)
        self.assertGreaterEqual(len(attempt.stage_residuals), 2)

    def test_build_staged_residual_candidates_covers_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "A.mo"
            source.write_text(SOURCE_TEXT, encoding="utf-8")
            rows = build_staged_residual_candidates([_source_row(source)], limit=3)

        self.assertEqual(len(rows), 3)
        self.assertEqual(
            {row["mutation_pattern"] for row in rows},
            {
                "staged_parameter_and_phantom_residual",
                "measurement_interface_then_behavioral_constraint_residual",
                "compound_structural_deficit_with_residual_symbol_exposure",
            },
        )

    def test_summarize_staged_residual_pack_requires_admission_and_residuals(self) -> None:
        rows = [
            {
                "mutation_pattern": f"p{i % 3}",
                "stage_residual_count": 2,
                "target_admission_status": "admitted_staged_residual_failure",
                "target_bucket_id": "ET03",
            }
            for i in range(9)
        ]

        summary = summarize_staged_residual_pack(rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["admitted_count"], 9)

    def test_run_staged_residual_pack_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "A.mo"
            inventory = root / "source_inventory.jsonl"
            out_dir = root / "out"
            source.write_text(SOURCE_TEXT, encoding="utf-8")
            inventory.write_text(
                "\n".join(json.dumps(_source_row(source)) for _ in range(3)),
                encoding="utf-8",
            )

            summary = run_staged_residual_pack(
                source_inventory_path=inventory,
                out_dir=out_dir,
                limit=9,
                run_check=_fake_check,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "staged_candidates.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
