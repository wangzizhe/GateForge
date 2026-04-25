from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_engineering_mutation_probe_v0_22_0 import (
    build_engineering_mutation_candidates,
    mutate_conditional_measurement_residual,
    mutate_measurement_abstraction_residual,
    mutate_parameter_lift_residual,
    run_engineering_mutation_probe,
    summarize_engineering_mutation_probe,
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
    return False, "Error: Variable not found in scope: residualSignal"


class EngineeringMutationProbeV0220Tests(unittest.TestCase):
    def test_measurement_abstraction_residual_changes_component_interface(self) -> None:
        attempt = mutate_measurement_abstraction_residual(SOURCE_TEXT)

        self.assertTrue(attempt.changed)
        self.assertIn("PowerSensor VS1", attempt.target_text)
        self.assertIn("aggregatePower", attempt.target_text)
        self.assertGreaterEqual(len(attempt.impact_points), 3)

    def test_conditional_measurement_residual_leaves_unguarded_downstream_use(self) -> None:
        attempt = mutate_conditional_measurement_residual(SOURCE_TEXT)

        self.assertTrue(attempt.changed)
        self.assertIn("VS1Optional if enableMeasurement", attempt.target_text)
        self.assertIn("connect(VS1.p, C1.p)", attempt.target_text)
        self.assertIn("optionalMeasurement = VS1Optional.v + measurementBias", attempt.target_text)
        self.assertGreaterEqual(len(attempt.impact_points), 3)

    def test_parameter_lift_residual_starts_scalar_to_vector_refactor(self) -> None:
        attempt = mutate_parameter_lift_residual(SOURCE_TEXT)

        self.assertTrue(attempt.changed)
        self.assertIn("parameter Real branchResistance = 100.0", attempt.target_text)
        self.assertIn("R=branchResistance[1]", attempt.target_text)
        self.assertGreaterEqual(len(attempt.impact_points), 3)

    def test_build_engineering_mutation_candidates_covers_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "A.mo"
            source.write_text(SOURCE_TEXT, encoding="utf-8")
            rows = build_engineering_mutation_candidates([_source_row(source)], limit=3)

        self.assertEqual(len(rows), 3)
        self.assertEqual(
            {row["mutation_pattern"] for row in rows},
            {
                "measurement_abstraction_residual",
                "conditional_measurement_residual",
                "parameter_lift_residual",
            },
        )
        self.assertEqual(
            {row["repair_eval_discipline"] for row in rows},
            {"agent_llm_omc_only_no_deterministic_repair"},
        )

    def test_summarize_engineering_mutation_probe_requires_admitted_coverage(self) -> None:
        rows = [
            {
                "mutation_pattern": f"p{i % 3}",
                "impact_point_count": 3,
                "target_admission_status": "admitted_engineering_mutation_failure",
                "target_bucket_id": "ET03",
            }
            for i in range(9)
        ]

        summary = summarize_engineering_mutation_probe(rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["admitted_count"], 9)
        self.assertEqual(summary["analysis_scope"], "mutation_construction_and_omc_failure_admission_only")

    def test_run_engineering_mutation_probe_writes_outputs(self) -> None:
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

            summary = run_engineering_mutation_probe(
                source_inventory_path=inventory,
                out_dir=out_dir,
                limit=9,
                run_check=_fake_check,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "engineering_candidates.jsonl").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
