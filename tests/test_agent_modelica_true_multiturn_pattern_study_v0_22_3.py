from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_true_multiturn_pattern_study_v0_22_3 import (
    build_pattern_rows,
    infer_mechanism,
    run_true_multiturn_pattern_study,
    summarize_patterns,
)


def _audit_row(candidate_id: str, run_dir: str, quality: str, sequence: list[str]) -> dict:
    return {
        "candidate_id": candidate_id,
        "run_dir": run_dir,
        "sample_quality": quality,
        "repair_round_count": 2,
        "n_turns": len(sequence),
        "observed_error_sequence": sequence,
        "false_multiturn_by_attempt_count": False,
    }


class TrueMultiturnPatternStudyV0223Tests(unittest.TestCase):
    def test_infer_mechanism_detects_cross_layer_measurement_case(self) -> None:
        row = _audit_row(
            "v0218_002_measurement_abstraction_partial_SmallRLStepV0",
            "complex",
            "true_multi_repair_pass",
            ["model_check_error", "constraint_violation", "none"],
        )

        self.assertEqual(infer_mechanism(row), "cross_layer_feedback_after_interface_repair")

    def test_build_pattern_rows_keeps_only_true_multiturn_passes(self) -> None:
        rows = [
            _audit_row("a", "raw_only_triple_trajectory_v0_19_45", "true_multi_repair_pass", ["x", "x"]),
            _audit_row("b", "run", "single_repair_then_validate", ["x", "none"]),
        ]

        patterns = build_pattern_rows(rows)

        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["mechanism"], "compound_residual_sequential_exposure")

    def test_summarize_patterns_recommends_rejecting_single_repair_validate(self) -> None:
        patterns = [
            {
                "candidate_id": "a",
                "run_dir": "r",
                "repair_round_count": 2,
                "n_turns": 2,
                "observed_error_sequence": ["x", "x"],
                "mechanism": "compound_residual_sequential_exposure",
            }
        ]
        audit_rows = [
            {
                "false_multiturn_by_attempt_count": True,
                "sample_quality": "single_repair_then_validate",
            }
        ]

        summary = summarize_patterns(patterns, audit_rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertIn("single repair then validate", " ".join(summary["recommended_construction_principles"]))

    def test_run_true_multiturn_pattern_study_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path = root / "audit.jsonl"
            out_dir = root / "out"
            audit_path.write_text(
                json.dumps(
                    _audit_row(
                        "v0218_002_measurement_abstraction_partial_SmallRLStepV0",
                        "complex",
                        "true_multi_repair_pass",
                        ["model_check_error", "constraint_violation", "none"],
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            summary = run_true_multiturn_pattern_study(audit_path=audit_path, out_dir=out_dir)

            self.assertEqual(summary["true_multi_case_count"], 1)
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "true_multiturn_patterns.jsonl").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
