from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_single_point_family_generalization_v0_22_8 import (
    build_family_generalization_candidates,
    mutate_capacitor_observability_refactor,
    mutate_sensor_output_abstraction_refactor,
    mutate_source_parameterization_refactor,
    run_family_generalization_pack,
    summarize_family_generalization_pack,
)


SOURCE_TEXT = """model A
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
    return False, "Error: Variable residual probe not found in scope A"


class SinglePointFamilyGeneralizationV0228Tests(unittest.TestCase):
    def test_mutators_create_distinct_single_point_families(self) -> None:
        attempts = [
            mutate_capacitor_observability_refactor(SOURCE_TEXT),
            mutate_sensor_output_abstraction_refactor(SOURCE_TEXT),
            mutate_source_parameterization_refactor(SOURCE_TEXT),
        ]

        self.assertTrue(all(attempt.changed for attempt in attempts))
        self.assertEqual(len({attempt.mutation_pattern for attempt in attempts}), 3)
        self.assertTrue(all(len(attempt.residual_chain) >= 2 for attempt in attempts))

    def test_build_family_generalization_candidates_covers_three_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "A.mo"
            source.write_text(SOURCE_TEXT, encoding="utf-8")
            rows = build_family_generalization_candidates([_source_row(source)], per_family_limit=1)

        self.assertEqual(len(rows), 3)
        self.assertEqual(len({row["mutation_pattern"] for row in rows}), 3)

    def test_summarize_family_generalization_pack_requires_patterns_and_admission(self) -> None:
        rows = [
            {
                "mutation_pattern": f"family_{index % 3}",
                "residual_count": 2,
                "target_admission_status": "admitted_single_point_family_failure",
                "target_bucket_id": "ET03",
            }
            for index in range(6)
        ]

        summary = summarize_family_generalization_pack(rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["admitted_count"], 6)

    def test_run_family_generalization_pack_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "A.mo"
            inventory = root / "source_inventory.jsonl"
            out_dir = root / "out"
            source.write_text(SOURCE_TEXT, encoding="utf-8")
            inventory.write_text("\n".join(json.dumps(_source_row(source)) for _ in range(3)), encoding="utf-8")

            summary = run_family_generalization_pack(
                source_inventory_path=inventory,
                out_dir=out_dir,
                per_family_limit=2,
                run_check=_fake_check,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "single_point_family_candidates.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
