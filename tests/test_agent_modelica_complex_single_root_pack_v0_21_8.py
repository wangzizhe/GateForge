from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_complex_single_root_pack_v0_21_8 import (
    build_complex_candidates,
    mutate_measurement_abstraction_partial,
    mutate_namespace_migration_partial,
    mutate_signal_source_migration_partial,
    run_complex_single_root_pack,
    summarize_complex_pack,
)


SOURCE_TEXT = """model A
  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10.0);
  Modelica.Electrical.Analog.Basic.Resistor R1(R=100.0);
  Modelica.Electrical.Analog.Sensors.VoltageSensor VS1;
equation
  connect(V1.p, R1.p);
  connect(VS1.p, R1.p);
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


class ComplexSingleRootPackV0218Tests(unittest.TestCase):
    def test_signal_source_migration_has_multiple_impacts(self) -> None:
        mutated, impacts = mutate_signal_source_migration_partial(SOURCE_TEXT)

        self.assertIn("SignalVoltage", mutated)
        self.assertIn("commandedVoltage", mutated)
        self.assertGreaterEqual(len(impacts), 3)

    def test_measurement_abstraction_has_multiple_residuals(self) -> None:
        mutated, impacts = mutate_measurement_abstraction_partial(SOURCE_TEXT)

        self.assertIn("aggregatePower", mutated)
        self.assertIn("measuredCurrent", mutated)
        self.assertGreaterEqual(len(impacts), 3)

    def test_namespace_migration_uses_plausible_incompatible_path(self) -> None:
        mutated, impacts = mutate_namespace_migration_partial(SOURCE_TEXT)

        self.assertIn("Analog.Ideal.Resistor", mutated)
        self.assertGreaterEqual(len(impacts), 3)

    def test_build_complex_candidates_cycles_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "A.mo"
            source.write_text(SOURCE_TEXT, encoding="utf-8")
            rows = build_complex_candidates([_source_row(source), _source_row(source), _source_row(source)])

        self.assertEqual(len(rows), 3)
        self.assertEqual({row["mutation_pattern"] for row in rows}, {
            "signal_source_migration_partial",
            "measurement_abstraction_partial",
            "namespace_migration_partial",
        })

    def test_summarize_complex_pack_requires_pattern_and_impact_coverage(self) -> None:
        rows = [
            {"mutation_pattern": "a", "impact_point_count": 3},
            {"mutation_pattern": "b", "impact_point_count": 3},
            {"mutation_pattern": "c", "impact_point_count": 3},
            {"mutation_pattern": "a", "impact_point_count": 3},
            {"mutation_pattern": "b", "impact_point_count": 3},
            {"mutation_pattern": "c", "impact_point_count": 3},
        ]

        summary = summarize_complex_pack(rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["repair_eval_discipline"], "agent_llm_omc_only_no_deterministic_repair")

    def test_run_complex_single_root_pack_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "A.mo"
            inventory = root / "source_inventory.jsonl"
            out_dir = root / "out"
            source.write_text(SOURCE_TEXT, encoding="utf-8")
            inventory.write_text(
                "\n".join(json.dumps(_source_row(source)) for _ in range(6)),
                encoding="utf-8",
            )

            summary = run_complex_single_root_pack(
                source_inventory_path=inventory,
                out_dir=out_dir,
                limit=6,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "complex_candidates.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
