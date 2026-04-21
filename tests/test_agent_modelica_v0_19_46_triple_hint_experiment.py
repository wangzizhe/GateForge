from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_triple_hint_experiment_v0_19_46 import (
    _build_summary,
    _load_existing_case_result,
)


class TestTripleHintExperimentV01946(unittest.TestCase):

    def test_load_existing_case_result_returns_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            self.assertIsNone(_load_existing_case_result(out_dir, "missing_case"))

    def test_load_existing_case_result_reads_saved_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            row = {
                "candidate_id": "case_1",
                "condition_a": {"fix_pass": False, "error_class": "service_error"},
                "condition_b": {"fix_pass": True, "error_class": ""},
            }
            (out_dir / "case_1.json").write_text(json.dumps(row), encoding="utf-8")
            self.assertEqual(_load_existing_case_result(out_dir, "case_1"), row)

    def test_build_summary_counts_passes_and_service_errors(self) -> None:
        results = [
            {
                "candidate_id": "case_1",
                "condition_a": {"fix_pass": False, "error_class": "service_error"},
                "condition_b": {"fix_pass": True, "error_class": ""},
            },
            {
                "candidate_id": "case_2",
                "condition_a": {"fix_pass": True, "error_class": ""},
                "condition_b": {"fix_pass": True, "error_class": ""},
            },
        ]
        summary = _build_summary(results)
        self.assertEqual(summary["version"], "v0.19.46")
        self.assertEqual(summary["n_cases"], 2)
        self.assertEqual(summary["condition_a"]["pass_n"], 1)
        self.assertEqual(summary["condition_a"]["pass_rate"], 0.5)
        self.assertEqual(summary["condition_a"]["service_errors"], 1)
        self.assertEqual(summary["condition_b"]["pass_n"], 2)
        self.assertEqual(summary["condition_b"]["pass_rate"], 1.0)
        self.assertEqual(summary["condition_b"]["service_errors"], 0)
        self.assertEqual(summary["delta"], 0.5)


if __name__ == "__main__":
    unittest.main()
