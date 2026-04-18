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


builder = _load_script("build_component_plus_connect_deletion_mutations_v0_19_28.py")


class TestComponentPlusConnectDeletionBuilder(unittest.TestCase):
    def test_extract_incident_non_sensor_connects_filters_ground_and_sensor(self) -> None:
        model_text = (
            "model Demo\n"
            "equation\n"
            "  connect(R1.p, V1.p);\n"
            "  connect(R1.n, C1.p);\n"
            "  connect(R1.n, G.p);\n"
            "  connect(VS1.p, R1.n);\n"
            "end Demo;\n"
        )
        rows = builder._extract_incident_non_sensor_connects(model_text, "R1")
        self.assertEqual([row.line for row in rows], ["connect(R1.p, V1.p);", "connect(R1.n, C1.p);"])
        self.assertEqual([row.kind for row in rows], ["source", "internal_branch"])

    def test_build_candidates_crosses_component_with_each_incident_non_sensor_connect(self) -> None:
        source_text = (
            "model Demo\n"
            "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10.0);\n"
            "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.1);\n"
            "equation\n"
            "  connect(R1.p, V1.p);\n"
            "  connect(R1.n, C1.p);\n"
            "  connect(C1.n, V1.n);\n"
            "end Demo;\n"
        )
        original_loader = builder._load_source_models
        try:
            builder._load_source_models = lambda: [(Path("demo.mo"), "Demo", source_text)]
            rows = builder._build_candidates()
        finally:
            builder._load_source_models = original_loader

        self.assertEqual(len(rows), 4)
        self.assertEqual(sorted(row.component.instance for row in rows), ["C1", "C1", "R1", "R1"])
        counts = sorted(row.incident_connect_count for row in rows)
        self.assertEqual(counts, [2, 2, 2, 2])

    def test_build_mutated_text_removes_both_rows(self) -> None:
        source_text = "a\nb\nc\nd\n"
        mutated = builder._build_mutated_text(source_text, 1, 2)
        self.assertEqual(mutated, "a\nd\n")

    def test_classify_check_failure_keeps_model_check_error_default(self) -> None:
        self.assertEqual(builder._classify_check_failure("undeclared component R1"), "model_check_error")
        self.assertEqual(
            builder._classify_check_failure("Class Demo has 8 equation(s) and 7 variable(s)."),
            "constraint_violation",
        )


if __name__ == "__main__":
    unittest.main()
