from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_run_mode_matrix_v0_26_3 import (
    RUN_MODES,
    build_run_mode_matrix,
    validate_run_mode_matrix,
)


class RunModeMatrixV0263Tests(unittest.TestCase):
    def test_run_mode_matrix_is_valid(self) -> None:
        self.assertEqual(validate_run_mode_matrix(RUN_MODES), [])

    def test_smoke_and_replay_do_not_report_pass_rate(self) -> None:
        self.assertFalse(RUN_MODES["smoke"]["may_report_pass_rate"])
        self.assertFalse(RUN_MODES["replay"]["may_report_pass_rate"])
        self.assertFalse(RUN_MODES["replay"]["llm_calls_allowed"])

    def test_missing_required_mode_is_rejected(self) -> None:
        matrix = dict(RUN_MODES)
        matrix.pop("raw_only")
        self.assertIn("missing_mode:raw_only", validate_run_mode_matrix(matrix))

    def test_build_matrix_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = build_run_mode_matrix(out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "run_mode_matrix_ready_for_harness_regression_ab")
            self.assertTrue(summary["discipline"]["smoke_is_not_capability_metric"])
            self.assertTrue((out_dir / "matrix.json").exists())
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
