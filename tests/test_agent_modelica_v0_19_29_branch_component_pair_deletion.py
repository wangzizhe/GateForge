from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    module_name = name.replace(".py", "")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


builder = _load_script("build_branch_component_pair_deletion_mutations_v0_19_29.py")


class TestBranchComponentPairDeletionBuilder(unittest.TestCase):
    def test_map_passive_components_only_keeps_basic_passive_parts(self) -> None:
        model_text = (
            "model Demo\n"
            "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10.0);\n"
            "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.1);\n"
            "  Modelica.Electrical.Analog.Sources.StepVoltage V1(V=1.0);\n"
            "equation\n"
            "end Demo;\n"
        )
        rows = builder._map_passive_components(model_text)
        self.assertEqual(sorted(rows.keys()), ["C1", "R1"])

    def test_build_candidates_uses_direct_passive_to_passive_connects(self) -> None:
        source_text = (
            "model Demo\n"
            "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10.0);\n"
            "  Modelica.Electrical.Analog.Basic.Inductor L1(L=0.1);\n"
            "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.1);\n"
            "equation\n"
            "  connect(R1.n, L1.p);\n"
            "  connect(L1.n, C1.p);\n"
            "  connect(C1.n, V1.n);\n"
            "end Demo;\n"
        )
        original_loader = builder._load_source_models
        try:
            builder._load_source_models = lambda: [(Path("demo.mo"), "Demo", source_text)]
            rows = builder._build_candidates()
        finally:
            builder._load_source_models = original_loader

        self.assertEqual(len(rows), 2)
        pairs = sorted(tuple(sorted(row.deleted_component_instances if hasattr(row, "deleted_component_instances") else [row.component_a.instance, row.component_b.instance])) for row in rows)
        self.assertEqual(pairs, [("C1", "L1"), ("L1", "R1")])

    def test_build_mutated_text_removes_two_component_rows(self) -> None:
        source_text = "a\nb\nc\nd\n"
        self.assertEqual(builder._build_mutated_text(source_text, 1, 2), "a\nd\n")

    def test_classify_check_failure_defaults_to_model_check_error(self) -> None:
        self.assertEqual(builder._classify_check_failure("undeclared class"), "model_check_error")
        self.assertEqual(
            builder._classify_check_failure("Class Demo has 8 equation(s) and 7 variable(s)."),
            "constraint_violation",
        )


if __name__ == "__main__":
    unittest.main()
