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


builder = _load_script("build_pair_connect_deletion_mutations_v0_19_27.py")


class TestPairConnectDeletionBuilder(unittest.TestCase):
    def test_extract_non_ground_non_sensor_connects_filters_ground_and_sensor(self) -> None:
        model_text = (
            "model Demo\n"
            "equation\n"
            "  connect(V1.p, R1.p);\n"
            "  connect(R1.n, C1.p);\n"
            "  connect(V1.n, G.p);\n"
            "  connect(VS1.p, C1.p);\n"
            "end Demo;\n"
        )
        rows = builder._extract_non_ground_non_sensor_connects(model_text)
        self.assertEqual([row.line for row in rows], ["connect(V1.p, R1.p);", "connect(R1.n, C1.p);"])
        self.assertEqual([row.kind for row in rows], ["source", "internal_branch"])

    def test_shared_endpoint_detects_exact_endpoint_overlap(self) -> None:
        row_a = builder.ConnectRow(
            index=0,
            line="connect(R1.n, C1.p);",
            kind="internal_branch",
            lhs="R1.n",
            rhs="C1.p",
        )
        row_b = builder.ConnectRow(
            index=1,
            line="connect(R1.n, L1.p);",
            kind="internal_branch",
            lhs="R1.n",
            rhs="L1.p",
        )
        self.assertEqual(builder._shared_endpoint(row_a, row_b), "R1.n")

    def test_build_pair_candidates_only_keeps_pairs_with_shared_endpoint(self) -> None:
        source_text = (
            "model Demo\n"
            "equation\n"
            "  connect(V1.p, R1.p);\n"
            "  connect(R1.n, C1.p);\n"
            "  connect(R1.n, L1.p);\n"
            "  connect(C1.n, L1.n);\n"
            "end Demo;\n"
        )
        original_loader = builder._load_source_models
        try:
            builder._load_source_models = lambda: [(Path("demo.mo"), "Demo", source_text)]
            pairs = builder._build_pair_candidates()
        finally:
            builder._load_source_models = original_loader

        self.assertEqual(len(pairs), 1)
        shared = sorted(pair.shared_endpoint for pair in pairs)
        self.assertEqual(shared, ["R1.n"])
        pair_lines = {
            tuple(sorted([pair.row_a.line, pair.row_b.line]))
            for pair in pairs
        }
        self.assertIn(
            tuple(sorted(["connect(R1.n, C1.p);", "connect(R1.n, L1.p);"])),
            pair_lines,
        )

    def test_classify_check_failure_promotes_overdetermined_to_constraint_violation(self) -> None:
        log_text = "Class Demo has 14 equation(s) and 13 variable(s).\n"
        self.assertEqual(builder._classify_check_failure(log_text), "constraint_violation")
        self.assertEqual(builder._classify_check_failure("undeclared connector foo"), "model_check_error")


if __name__ == "__main__":
    unittest.main()
