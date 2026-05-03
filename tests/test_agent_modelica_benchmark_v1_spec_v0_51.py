from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_v1_spec_v0_51_0 import (
    build_benchmark_v1_spec,
    classify_result_for_scoring,
    run_benchmark_v1_spec,
    validate_result_record,
    validate_task_record,
)


class BenchmarkV1SpecV051Tests(unittest.TestCase):
    def test_spec_requires_medium_layer_and_forbids_hard_only_benchmark(self) -> None:
        summary = build_benchmark_v1_spec()
        layers = [layer["layer"] for layer in summary["difficulty_layers"]]
        self.assertIn("medium", layers)
        self.assertIn("hard", layers)
        self.assertTrue(summary["comparison_contract"]["medium_layer_must_exist"])
        self.assertTrue(summary["comparison_contract"]["hard_pack_must_not_be_only_benchmark"])
        self.assertFalse(summary["conclusion_allowed"])

    def test_task_record_validation_blocks_prompt_leakage(self) -> None:
        task = {
            "case_id": "case_a",
            "title": "Repair task",
            "visible_task_description": "Repair the Modelica model.",
            "constraints": ["Keep public interface unchanged."],
            "initial_model": "model Demo end Demo;",
            "difficulty_layer": "medium",
            "source_backed": True,
            "model_check_first": True,
            "blind_lint_status": "PASS",
            "admission_status": "admitted_via_omc",
            "dataset_split": "dev",
            "hidden_oracle": {"reference": "not prompt visible"},
        }
        self.assertIn("prompt_leak_field:hidden_oracle", validate_task_record(task))
        task.pop("hidden_oracle")
        self.assertEqual(validate_task_record(task), [])

    def test_result_scoring_separates_provider_and_task_failures(self) -> None:
        provider_result = {
            "case_id": "case_a",
            "agent_name": "agent",
            "llm_model": "model",
            "difficulty_layer": "medium",
            "dataset_split": "holdout",
            "final_verdict": "PROVIDER_ERROR",
            "submitted": False,
            "provider_status": "provider_unstable",
            "omc_invocation_count": 0,
            "failure_category": "provider_error",
        }
        self.assertEqual(validate_result_record(provider_result), [])
        scored = classify_result_for_scoring(provider_result)
        self.assertEqual(scored["score_bucket"], "provider_excluded")
        self.assertFalse(scored["counts_as_capability_failure"])
        fail_result = dict(provider_result, final_verdict="FAIL", provider_status="provider_stable", failure_category="model_check_error")
        scored_fail = classify_result_for_scoring(fail_result)
        self.assertEqual(scored_fail["score_bucket"], "capability_failure")
        self.assertTrue(scored_fail["counts_as_capability_failure"])

    def test_run_benchmark_v1_spec_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_benchmark_v1_spec(out_dir=Path(tmp))
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((Path(tmp) / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
