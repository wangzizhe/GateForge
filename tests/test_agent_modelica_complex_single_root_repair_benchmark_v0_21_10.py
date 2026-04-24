from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_complex_single_root_repair_benchmark_v0_21_10 import (
    build_repair_benchmark,
    build_repair_case,
    run_complex_single_root_repair_benchmark_builder,
)


def _admitted_row() -> dict:
    return {
        "candidate_id": "v0218_a",
        "mutation_pattern": "signal_source_migration_partial",
        "source_model_path": "/tmp/source.mo",
        "target_model_path": "/tmp/target.mo",
        "target_bucket_id": "ET02",
        "target_admission_status": "admitted_complex_target_failure",
    }


class ComplexSingleRootRepairBenchmarkV02110Tests(unittest.TestCase):
    def test_build_repair_case_omits_hidden_root_cause_metadata(self) -> None:
        case = build_repair_case(_admitted_row())

        self.assertIsNotNone(case)
        assert case is not None
        self.assertEqual(case["benchmark_family"], "complex_single_root_refactor_residual")
        self.assertNotIn("root_cause_shape", case)
        self.assertNotIn("impact_points", case)
        self.assertNotIn("repair_actions", case)

    def test_build_repair_benchmark_skips_non_admitted_targets(self) -> None:
        rows = [_admitted_row(), {**_admitted_row(), "target_admission_status": "rejected"}]

        cases = build_repair_benchmark(rows)

        self.assertEqual(len(cases), 1)

    def test_run_complex_single_root_repair_benchmark_builder_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            admission_path = root / "admission.jsonl"
            out_dir = root / "out"
            admission_path.write_text(json.dumps(_admitted_row()), encoding="utf-8")

            summary = run_complex_single_root_repair_benchmark_builder(
                admission_path=admission_path,
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "admitted_cases.jsonl").exists())
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
