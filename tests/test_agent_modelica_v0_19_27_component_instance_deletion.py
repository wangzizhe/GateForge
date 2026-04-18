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


builder = _load_script("build_component_instance_deletion_mutations_v0_19_27.py")


class TestComponentInstanceDeletionBuilder(unittest.TestCase):
    def test_extract_passive_components_excludes_sources_sensors_and_ground(self) -> None:
        model_text = (
            "model Demo\n"
            "  Modelica.Electrical.Analog.Sources.StepVoltage V1(V=1.0);\n"
            "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10.0);\n"
            "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.1);\n"
            "  Modelica.Electrical.Analog.Sensors.VoltageSensor VS1;\n"
            "  Modelica.Electrical.Analog.Basic.Ground G;\n"
            "equation\n"
            "end Demo;\n"
        )
        rows = builder._extract_passive_components(model_text)
        self.assertEqual([(row.instance, row.component_kind) for row in rows], [("R1", "resistor"), ("C1", "capacitor")])

    def test_count_instance_connects_counts_exact_instance_references(self) -> None:
        model_text = (
            "model Demo\n"
            "equation\n"
            "  connect(R1.p, V1.p);\n"
            "  connect(R1.n, C1.p);\n"
            "  connect(R2.n, C1.n);\n"
            "end Demo;\n"
        )
        self.assertEqual(builder._count_instance_connects(model_text, "R1"), 2)
        self.assertEqual(builder._count_instance_connects(model_text, "C1"), 2)
        self.assertEqual(builder._count_instance_connects(model_text, "R2"), 1)

    def test_build_candidates_keeps_only_components_with_two_or_more_connects(self) -> None:
        source_text = (
            "model Demo\n"
            "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10.0);\n"
            "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.1);\n"
            "  Modelica.Electrical.Analog.Basic.Inductor L1(L=0.1);\n"
            "equation\n"
            "  connect(R1.p, V1.p);\n"
            "  connect(R1.n, C1.p);\n"
            "  connect(C1.n, G.p);\n"
            "  connect(L1.p, V1.p);\n"
            "end Demo;\n"
        )
        original_loader = builder._load_source_models
        try:
            builder._load_source_models = lambda: [(Path("demo.mo"), "Demo", source_text)]
            rows = builder._build_candidates()
        finally:
            builder._load_source_models = original_loader

        self.assertEqual([row.component.instance for row in rows], ["R1", "C1"])

    def test_classify_check_failure_defaults_to_model_check_error(self) -> None:
        self.assertEqual(builder._classify_check_failure("undeclared component R2"), "model_check_error")
        self.assertEqual(
            builder._classify_check_failure("Class Demo has 9 equation(s) and 8 variable(s)."),
            "constraint_violation",
        )


if __name__ == "__main__":
    unittest.main()
