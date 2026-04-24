from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_complex_single_root_admission_v0_21_9 import (
    admit_complex_candidate,
    run_complex_single_root_admission,
    summarize_admission,
)


def _candidate(path: Path) -> dict:
    return {
        "candidate_id": "v0218_a",
        "mutation_pattern": "signal_source_migration_partial",
        "root_cause_shape": "single_refactor_intent_with_multiple_consistency_residuals",
        "impact_point_count": 3,
        "source_model_path": "source.mo",
        "target_model_path": str(path),
        "target_model_name": "A",
    }


class ComplexSingleRootAdmissionV0219Tests(unittest.TestCase):
    def test_admit_complex_candidate_accepts_classified_check_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.mo"
            path.write_text("model A\nend A;", encoding="utf-8")

            row = admit_complex_candidate(
                _candidate(path),
                run_check=lambda _text, _name: (False, "Error: Variable x not found in scope A."),
            )

        self.assertEqual(row["target_bucket_id"], "ET03")
        self.assertEqual(row["target_admission_status"], "admitted_complex_target_failure")

    def test_admit_complex_candidate_rejects_unclassified_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.mo"
            path.write_text("model A\nend A;", encoding="utf-8")

            row = admit_complex_candidate(
                _candidate(path),
                run_check=lambda _text, _name: (False, "unknown diagnostic"),
            )

        self.assertEqual(row["target_admission_status"], "rejected_target_not_classified")

    def test_summarize_admission_passes_when_most_targets_admit(self) -> None:
        rows = [
            {"target_admission_status": "admitted_complex_target_failure", "mutation_pattern": "a", "target_bucket_id": "ET03"},
            {"target_admission_status": "admitted_complex_target_failure", "mutation_pattern": "b", "target_bucket_id": "ET02"},
            {"target_admission_status": "rejected_target_not_classified", "mutation_pattern": "c", "target_bucket_id": "UNCLASSIFIED"},
        ]

        summary = summarize_admission(rows)

        self.assertEqual(summary["status"], "REVIEW")
        self.assertEqual(summary["admission_pass_rate"], 0.666667)

    def test_run_complex_single_root_admission_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_path = root / "A.mo"
            candidate_path = root / "candidates.jsonl"
            out_dir = root / "out"
            model_path.write_text("model A\nend A;", encoding="utf-8")
            candidate_path.write_text(json.dumps(_candidate(model_path)), encoding="utf-8")

            summary = run_complex_single_root_admission(
                complex_candidate_path=candidate_path,
                out_dir=out_dir,
                run_check=lambda _text, _name: (False, "Error: Variable x not found in scope A."),
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "admitted_complex_targets.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
