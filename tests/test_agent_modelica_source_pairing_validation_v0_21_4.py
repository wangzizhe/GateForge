from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_source_pairing_validation_v0_21_4 import (
    build_source_pair,
    extract_embedded_model_text,
    run_source_pairing_validation,
    summarize_validations,
    validate_pair,
)


def _family_candidate() -> dict:
    return {
        "family_candidate_id": "v0211_a",
        "source_task_id": "task_a",
        "bucket_id": "ET01",
    }


def _task_row(model_text: str) -> dict:
    return {
        "task_id": "task_a",
        "model_name": "A",
        "model_text": model_text,
        "omc_output_excerpt": "Error: Parser error: unexpected token",
        "classification": {"bucket_id": "ET01"},
    }


class SourcePairingValidationV0214Tests(unittest.TestCase):
    def test_extract_embedded_model_text_reads_json_wrapper(self) -> None:
        text = extract_embedded_model_text(json.dumps({"model_text": "model A\nend A;"}))

        self.assertEqual(text, "model A\nend A;")

    def test_build_source_pair_uses_embedded_model_only(self) -> None:
        pair = build_source_pair(_family_candidate(), _task_row(json.dumps({"model_text": "model A\nend A;"})))

        self.assertEqual(pair["source_pairing_method"], "embedded_json_model_text")
        self.assertEqual(pair["source_model_name"], "A")

    def test_build_source_pair_does_not_repair_plain_failed_model(self) -> None:
        pair = build_source_pair(_family_candidate(), _task_row("model A\n  Real x;\nequation\n x = ;\nend A;"))

        self.assertEqual(pair["source_pairing_method"], "none_available_without_repair")
        self.assertEqual(pair["source_model_text"], "")

    def test_validate_pair_promotes_only_when_source_and_target_are_verified(self) -> None:
        pair = build_source_pair(_family_candidate(), _task_row(json.dumps({"model_text": "model A\nend A;"})))

        row = validate_pair(pair, run_check=lambda _text, _name: (True, "Check of A completed successfully."))

        self.assertEqual(row["source_viability_status"], "verified_clean_source")
        self.assertEqual(row["target_failure_status"], "verified_target_failure")
        self.assertEqual(row["main_benchmark_status"], "main_admissible_source_target_pair")

    def test_summarize_validations_reports_blocked_when_no_main_pairs(self) -> None:
        summary = summarize_validations(
            [
                {
                    "main_benchmark_status": "blocked_from_main_benchmark",
                    "source_viability_status": "source_not_viable",
                    "target_failure_status": "verified_target_failure",
                    "bucket_id": "ET01",
                }
            ]
        )

        self.assertEqual(summary["main_admissible_count"], 0)
        self.assertEqual(summary["benchmark_admission_decision"], "do_not_promote_to_main_benchmark")

    def test_run_source_pairing_validation_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            family_path = root / "family.jsonl"
            task_dir = root / "tasks"
            out_dir = root / "out"
            task_dir.mkdir()
            family_path.write_text(json.dumps(_family_candidate()), encoding="utf-8")
            (task_dir / "task_a.json").write_text(
                json.dumps(_task_row(json.dumps({"model_text": "model A\nend A;"}))),
                encoding="utf-8",
            )

            summary = run_source_pairing_validation(
                family_candidate_path=family_path,
                generation_task_dir=task_dir,
                out_dir=out_dir,
                run_check=lambda _text, _name: (True, "Check of A completed successfully."),
            )

            self.assertEqual(summary["main_admissible_count"], 1)
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "validated_pairs.jsonl").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
