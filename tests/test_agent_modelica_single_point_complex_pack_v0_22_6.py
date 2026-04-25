from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_single_point_complex_pack_v0_22_6 import (
    build_single_point_complex_candidates,
    mutate_single_point_resistor_observability_refactor,
    run_single_point_complex_pack,
    source_complexity_class,
    summarize_single_point_complex_pack,
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
    return False, "Error: Variable R1ResidualProbe not found in scope A"


class SinglePointComplexPackV0226Tests(unittest.TestCase):
    def test_single_point_mutation_keeps_residuals_coupled_to_one_scope(self) -> None:
        attempt = mutate_single_point_resistor_observability_refactor(SOURCE_TEXT)

        self.assertTrue(attempt.changed)
        self.assertEqual(attempt.refactor_scope, "R1_observability_refactor")
        self.assertIn("R1Resistance[1]", attempt.target_text)
        self.assertIn("R1ResidualProbe", attempt.target_text)
        self.assertGreaterEqual(len(attempt.residual_chain), 2)

    def test_source_complexity_class_uses_component_count(self) -> None:
        self.assertEqual(source_complexity_class(SOURCE_TEXT), "small")
        self.assertEqual(
            source_complexity_class(
                SOURCE_TEXT + "  Modelica.Electrical.Analog.Basic.Resistor R2(R=200.0);\n"
            ),
            "medium",
        )

    def test_build_single_point_complex_candidates_marks_scope_and_rationale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "A.mo"
            source.write_text(SOURCE_TEXT, encoding="utf-8")
            rows = build_single_point_complex_candidates([_source_row(source)], limit=1)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mutation_pattern"], "single_point_resistor_observability_refactor")
        self.assertIn("single_point_refactor_scope", rows[0])
        self.assertIn("residual_coupling_rationale", rows[0])

    def test_summarize_single_point_complex_pack_requires_admission(self) -> None:
        rows = [
            {
                "residual_count": 2,
                "source_complexity_class": "small",
                "target_admission_status": "admitted_single_point_complex_failure",
                "target_bucket_id": "ET03",
            }
            for _ in range(6)
        ]

        summary = summarize_single_point_complex_pack(rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["admitted_count"], 6)

    def test_run_single_point_complex_pack_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = root / "source_inventory.jsonl"
            out_dir = root / "out"
            rows = []
            for index in range(6):
                source = root / f"A{index}.mo"
                source.write_text(SOURCE_TEXT.replace("model A", f"model A{index}").replace("end A;", f"end A{index};"), encoding="utf-8")
                rows.append(json.dumps(_source_row(source)))
            inventory.write_text("\n".join(rows), encoding="utf-8")

            summary = run_single_point_complex_pack(
                source_inventory_path=inventory,
                out_dir=out_dir,
                limit=6,
                run_check=_fake_check,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "single_point_candidates.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
