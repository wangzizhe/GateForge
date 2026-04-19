from __future__ import annotations

import unittest
from pathlib import Path

from scripts.build_equation_deletion_mutations_v0_19_31 import (
    OPENIPSL_LIBRARY_ROOT,
    SourceSpec,
    _build_pair_candidates,
    _classify_failure,
    _extract_qualified_model_name,
    _find_equation_candidates,
    _infer_library_model_path,
    _is_core_equation,
    _lhs_signature,
)


class TestV01931EquationDeletion(unittest.TestCase):
    def test_extract_qualified_model_name(self):
        text = "within OpenIPSL.Electrical.Banks.PSSE;\nmodel CSVGN1\nend CSVGN1;\n"
        self.assertEqual(
            _extract_qualified_model_name(text),
            "OpenIPSL.Electrical.Banks.PSSE.CSVGN1",
        )

    def test_infer_library_model_path(self):
        path = _infer_library_model_path(
            OPENIPSL_LIBRARY_ROOT,
            "OpenIPSL.Electrical.Banks.PSSE.CSVGN1",
        )
        self.assertEqual(
            path,
            OPENIPSL_LIBRARY_ROOT / "Electrical" / "Banks" / "PSSE" / "CSVGN1.mo",
        )

    def test_lhs_signature(self):
        self.assertEqual(_lhs_signature("der(Epq) = 1/Tpd0*(EFD - XadIfd);"), "der_epq")
        self.assertEqual(_lhs_signature("[p.ir; p.ii] = foo;"), "p_ir_p_ii")

    def test_classify_failure(self):
        self.assertEqual(
            _classify_failure("Class A has 10 equation(s) and 11 variable(s)."),
            "underdetermined",
        )
        self.assertEqual(
            _classify_failure("Class A has 12 equation(s) and 11 variable(s)."),
            "overdetermined",
        )

    def test_find_equation_candidates_from_genroe(self):
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
        )
        candidates = _find_equation_candidates(spec)
        lines = {row.line_text.strip() for row in candidates}
        self.assertIn("der(Epd) = 0;", lines)
        self.assertIn("der(Epq) = 1/Tpd0*(EFD - XadIfd);", lines)
        self.assertIn("PSId = PSIppd - Xppd*id;", lines)

    def test_find_equation_candidates_from_csvgn1(self):
        source_path = (
            Path("assets_private/agent_modelica_cross_domain_openipsl_v1_fixture_v1/source_models/CSVGN1_dc3e8a4ebd.mo").resolve()
        )
        if not source_path.exists():
            self.skipTest("assets_private not available in this environment")
        spec = SourceSpec(
            source_file=source_path.name,
            source_path=source_path,
            library_root=OPENIPSL_LIBRARY_ROOT,
            package_name="OpenIPSL",
            qualified_model_name="OpenIPSL.Electrical.Banks.PSSE.CSVGN1",
            source_library_model_path=OPENIPSL_LIBRARY_ROOT / "Electrical" / "Banks" / "PSSE" / "CSVGN1.mo",
        )
        candidates = _find_equation_candidates(spec)
        lines = {row.line_text.strip() for row in candidates}
        self.assertIn("k50 = (CBASE/S_b - Y0)/(MBASE/S_b);", lines)
        self.assertIn("vq = id/Y;", lines)
        self.assertIn("-Q = p.vi*p.ir - p.vr*p.ii;", lines)

    def test_build_pair_candidates_uses_core_equations(self):
        source_path = (
            Path("assets_private/agent_modelica_cross_domain_openipsl_v1_fixture_v1/source_models/CSVGN1_dc3e8a4ebd.mo").resolve()
        )
        if not source_path.exists():
            self.skipTest("assets_private not available in this environment")
        spec = SourceSpec(
            source_file=source_path.name,
            source_path=source_path,
            library_root=OPENIPSL_LIBRARY_ROOT,
            package_name="OpenIPSL",
            qualified_model_name="OpenIPSL.Electrical.Banks.PSSE.CSVGN1",
            source_library_model_path=OPENIPSL_LIBRARY_ROOT / "Electrical" / "Banks" / "PSSE" / "CSVGN1.mo",
        )
        singles = _find_equation_candidates(spec)
        core = [row for row in singles if _is_core_equation(row)]
        pairs = _build_pair_candidates(spec)
        self.assertEqual(len(core), 6)
        self.assertEqual(len(pairs), 15)


if __name__ == "__main__":
    unittest.main()
