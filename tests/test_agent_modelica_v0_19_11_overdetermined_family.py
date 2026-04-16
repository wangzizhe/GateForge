from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class V01911OverdeterminedFamilyTests(unittest.TestCase):
    def test_turn_shape_marks_single_fix_closure(self) -> None:
        semantics = _load_script("build_turn_semantics_report_v0_19_11.py")

        self.assertEqual(
            semantics.classify_turn_shape(
                {
                    "executor_status": "PASS",
                    "n_turns": 2,
                    "observed_error_sequence": ["model_check_error", "none"],
                }
            ),
            "single_fix_closure",
        )
        self.assertEqual(
            semantics.classify_turn_shape(
                {
                    "executor_status": "PASS",
                    "n_turns": 3,
                    "observed_error_sequence": ["model_check_error", "model_check_error", "none"],
                }
            ),
            "requires_multiple_llm_repairs",
        )

    def test_overdetermined_specs_use_structural_relations_not_literal_bindings(self) -> None:
        builder = _load_script("build_overdetermined_mutations_v0_19_11.py")

        # 8 KVL + 4 KCL specs
        self.assertEqual(len(builder.SPECS), 12)
        kvl_specs = [s for s in builder.SPECS if "kvl" in s.relation_id]
        kcl_specs = [s for s in builder.SPECS if "kcl" in s.relation_id]
        self.assertEqual(len(kvl_specs), 8)
        self.assertEqual(len(kcl_specs), 4)
        for spec in builder.SPECS:
            self.assertNotIn("= 0.0;", spec.redundant_equation)
            self.assertIn("=", spec.redundant_equation)
            self.assertGreaterEqual(spec.redundant_equation.count("."), 2)

    def test_extract_structural_counts_and_overdetermined_detection(self) -> None:
        builder = _load_script("build_overdetermined_mutations_v0_19_11.py")
        log_text = (
            "Error: Too many equations, over-determined system. "
            "The model has 29 equation(s) and 28 variable(s)."
        )

        counts = builder._extract_structural_counts(log_text)

        self.assertEqual(counts, {"equations": 29, "variables": 28})
        self.assertTrue(builder._is_overdetermined_failure(log_text))

    def test_overdetermined_report_summarises_resolution_shapes(self) -> None:
        report_mod = _load_script("build_overdetermined_report_v0_19_11.py")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            benchmark = tmp / "cases.jsonl"
            summary = tmp / "summary.json"
            turn_semantics = tmp / "turn.json"
            benchmark.write_text(
                (
                    '{"candidate_id":"c1","overdetermined_relation_id":"r1","redundant_relation_equation":"R1.v + C1.v = V1.v;"}\n'
                    '{"candidate_id":"c2","overdetermined_relation_id":"r2","redundant_relation_equation":"L1.v + R1.v = V1.v;"}\n'
                ),
                encoding="utf-8",
            )
            summary.write_text(
                '{"summaries":['
                '{"candidate_id":"c1","executor_status":"PASS","n_turns":2,"observed_error_sequence":["constraint_violation","none"]},'
                '{"candidate_id":"c2","executor_status":"FAILED","n_turns":1,"observed_error_sequence":["constraint_violation"]}'
                ']}',
                encoding="utf-8",
            )
            turn_semantics.write_text('{"by_family":{"component_modifier_name_error":{"turn_shape_counts":{"single_fix_closure":8}}}}', encoding="utf-8")

            report_mod.TURN_SEMANTICS_JSON = turn_semantics
            report, records = report_mod.build_report(benchmark_path=benchmark, summary_path=summary)

        self.assertEqual(report["pass_count"], 1)
        self.assertEqual(report["resolution_shape_counts"]["single_fix_closure"], 1)
        self.assertEqual(report["resolution_shape_counts"]["unresolved"], 1)
        self.assertEqual(report["unresolved_case_ids"], ["c2"])
        self.assertEqual(len(records), 2)


if __name__ == "__main__":
    unittest.main()
