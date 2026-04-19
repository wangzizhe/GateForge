from __future__ import annotations

import unittest
from pathlib import Path

from scripts.build_parameter_deletion_mutations_v0_19_30 import (
    BUILDINGS_LIBRARY_ROOT,
    OPENIPSL_LIBRARY_ROOT,
    SourceSpec,
    _extract_qualified_model_name,
    _find_parameter_candidates,
    _infer_library_model_path,
    _passes_symptom_root_cause_gate,
)


class TestV01930ParameterDeletion(unittest.TestCase):
    def test_extract_qualified_model_name(self):
        text = "within OpenIPSL.Electrical.Machines.PSSE;\nmodel GENROE\nend GENROE;\n"
        self.assertEqual(
            _extract_qualified_model_name(text),
            "OpenIPSL.Electrical.Machines.PSSE.GENROE",
        )

    def test_infer_library_model_path(self):
        path = _infer_library_model_path(
            OPENIPSL_LIBRARY_ROOT,
            "OpenIPSL.Electrical.Machines.PSSE.GENROE",
        )
        self.assertEqual(
            path,
            OPENIPSL_LIBRARY_ROOT / "Electrical" / "Machines" / "PSSE" / "GENROE.mo",
        )

    def test_symptom_root_cause_gate_requires_other_line(self):
        self.assertEqual(
            _passes_symptom_root_cause_gate("[/workspace/model.mo:41:3-41:10] Error\n", 41),
            (False, [41]),
        )
        self.assertEqual(
            _passes_symptom_root_cause_gate(
                "[/workspace/model.mo:41:3-41:10] Error\n[/workspace/model.mo:88:5-88:12] Error\n",
                41,
            ),
            (True, [41, 88]),
        )

    def test_find_parameter_candidates_on_openipsl_fixture(self):
        source_path = (
            Path("assets_private/agent_modelica_cross_domain_openipsl_v1_fixture_v1/source_models/GENROE_12c13f38c4.mo").resolve()
        )
        if not source_path.exists():
            self.skipTest("assets_private not available in this environment")
        spec = SourceSpec(
            source_file=source_path.name,
            source_path=source_path,
            library_root=OPENIPSL_LIBRARY_ROOT,
            package_name="OpenIPSL",
            qualified_model_name="OpenIPSL.Electrical.Machines.PSSE.GENROE",
            source_library_model_path=OPENIPSL_LIBRARY_ROOT / "Electrical" / "Machines" / "PSSE" / "GENROE.mo",
            source_family="openipsl",
            viability_group="cross_domain",
        )
        candidates = _find_parameter_candidates(spec)
        names = {row.parameter_name for row in candidates}
        self.assertIn("efd0", names)
        self.assertIn("Zs", names)

    def test_find_parameter_candidates_on_msl_fallback_source(self):
        source_path = (
            Path("artifacts/agent_modelica_electrical_frozen_taskset_v1_smoke/source_models/medium_triple_sensor_v0.mo").resolve()
        )
        if not source_path.exists():
            self.skipTest("artifact source models not available in this environment")
        spec = SourceSpec(
            source_file=source_path.name,
            source_path=source_path,
            library_root=None,
            package_name="",
            qualified_model_name="MediumTripleSensorV0",
            source_library_model_path=None,
            source_family="msl_electrical",
            viability_group="msl_fallback",
        )
        candidates = _find_parameter_candidates(spec)
        names = {row.parameter_name for row in candidates}
        self.assertEqual(names, {"R1_val", "R2_val", "R3_val", "C1_val"})

    def test_buildings_model_path_resolution(self):
        path = _infer_library_model_path(
            BUILDINGS_LIBRARY_ROOT,
            "Buildings.Controls.Continuous.Examples.LimPIDWithReset",
        )
        self.assertEqual(
            path,
            BUILDINGS_LIBRARY_ROOT / "Controls" / "Continuous" / "Examples" / "LimPIDWithReset.mo",
        )


if __name__ == "__main__":
    unittest.main()
