from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_source_backed_target_admission_v0_21_6 import (
    run_source_backed_target_admission,
    summarize_target_admission,
    validate_target_candidate,
)


def _candidate(path: Path, bucket_id: str = "ET01") -> dict:
    return {
        "source_backed_candidate_id": "v0215_a",
        "family_candidate_id": "fam_a",
        "bucket_id": bucket_id,
        "source_model_path": "source.mo",
        "target_model_path": str(path),
        "target_model_name": "A",
        "source_viability_status": "historically_verified_clean_source",
    }


class SourceBackedTargetAdmissionV0216Tests(unittest.TestCase):
    def test_validate_target_candidate_marks_matching_failure_as_main_admissible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.mo"
            path.write_text("{\nmodel A\nend A;", encoding="utf-8")

            row = validate_target_candidate(
                _candidate(path, "ET01"),
                run_check=lambda _text, _name: (False, "Error: Parser error: unexpected token"),
            )

        self.assertEqual(row["target_reclassified_bucket"], "ET01")
        self.assertEqual(row["benchmark_admission_status"], "main_admissible_source_target_pair")

    def test_validate_target_candidate_blocks_bucket_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A.mo"
            path.write_text("model A\nend A;", encoding="utf-8")

            row = validate_target_candidate(
                _candidate(path, "ET03"),
                run_check=lambda _text, _name: (False, "Error: Parser error: unexpected token"),
            )

        self.assertEqual(row["benchmark_admission_status"], "blocked_from_main_benchmark")

    def test_summarize_target_admission_reports_full_pass(self) -> None:
        summary = summarize_target_admission(
            [
                {
                    "benchmark_admission_status": "main_admissible_source_target_pair",
                    "bucket_id": "ET01",
                    "target_failure_verified": True,
                }
            ]
        )

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["main_admissible_count"], 1)

    def test_run_source_backed_target_admission_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_path = root / "A.mo"
            source_backed_path = root / "source_backed.jsonl"
            out_dir = root / "out"
            model_path.write_text("{\nmodel A\nend A;", encoding="utf-8")
            source_backed_path.write_text(json.dumps(_candidate(model_path, "ET01")), encoding="utf-8")

            summary = run_source_backed_target_admission(
                source_backed_path=source_backed_path,
                out_dir=out_dir,
                run_check=lambda _text, _name: (False, "Error: Parser error: unexpected token"),
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "target_admission.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
