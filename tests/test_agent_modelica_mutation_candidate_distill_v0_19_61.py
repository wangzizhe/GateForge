from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_mutation_candidate_distill_v0_19_61 import (
    build_candidates,
    build_distill_summary,
    build_mutation_candidate,
    evaluate_candidate_admission,
    run_mutation_candidate_distill,
)


def _source_row(
    task_id: str = "task_a",
    bucket_id: str = "ET01",
    final_status: str = "fail",
    evidence: str = "Missing token: ';'",
) -> dict:
    return {
        "task_id": task_id,
        "difficulty": "T1",
        "domain": "electrical",
        "final_status": final_status,
        "model_name": "GeneratedModel",
        "model_text": "model GeneratedModel\n Real x;\nequation\n x = 1;\nend GeneratedModel;",
        "classification": {
            "bucket_id": bucket_id,
            "classification_source": "omc_output",
            "evidence_excerpt": evidence,
        },
        "omc_output_excerpt": evidence,
    }


class MutationCandidateDistillV01961Tests(unittest.TestCase):
    def test_build_mutation_candidate_from_gap_bucket(self) -> None:
        candidate = build_mutation_candidate(_source_row(bucket_id="ET02"))

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate["proposed_mutation_family"], "missing_component_or_library_reference")
        self.assertEqual(candidate["priority_bucket"], "main_gap_bucket")
        self.assertEqual(candidate["benchmark_admission_status"], "admitted")

    def test_build_mutation_candidate_skips_pass(self) -> None:
        self.assertIsNone(build_mutation_candidate(_source_row(final_status="pass", bucket_id="PASS")))

    def test_evaluate_candidate_admission_rejects_unlinked_evidence(self) -> None:
        row = _source_row(evidence="")
        candidate = {
            "source_task_id": row["task_id"],
            "bucket_id": "ET01",
            "proposed_mutation_family": "generation_parse_load_failure",
            "observed_failure_excerpt": "",
            "isolation_status": "isolated_candidate_pool_only",
        }

        admission = evaluate_candidate_admission(candidate, row)

        self.assertEqual(admission["status"], "rejected")
        self.assertIn("workflow_proximal", admission["rejection_reasons"])

    def test_build_candidates_keeps_supported_failure_buckets(self) -> None:
        candidates = build_candidates(
            [
                _source_row("a", "ET01"),
                _source_row("b", "ET03", evidence="Error: Variable y not found in scope"),
                _source_row("c", "ET99"),
                _source_row("d", "PASS", final_status="pass"),
            ]
        )

        self.assertEqual([row["bucket_id"] for row in candidates], ["ET01", "ET03"])

    def test_build_distill_summary_reports_pass_rate(self) -> None:
        rows = [_source_row("a", "ET01"), _source_row("b", "ET02"), _source_row("c", "ET03")]
        candidates = build_candidates(rows)

        summary = build_distill_summary(candidates, rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["candidate_count"], 3)
        self.assertEqual(summary["admitted_count"], 3)
        self.assertEqual(summary["admission_pass_rate"], 1.0)

    def test_run_mutation_candidate_distill_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "generation"
            tasks_dir = input_dir / "tasks"
            tasks_dir.mkdir(parents=True)
            for row in [_source_row("a", "ET01"), _source_row("b", "ET02"), _source_row("c", "ET03")]:
                (tasks_dir / f"{row['task_id']}.json").write_text(json.dumps(row), encoding="utf-8")
            out_dir = root / "out"

            summary = run_mutation_candidate_distill(input_dir=input_dir, out_dir=out_dir)

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "candidates.jsonl").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()

