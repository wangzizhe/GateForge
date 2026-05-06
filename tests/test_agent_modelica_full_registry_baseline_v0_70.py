from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_full_registry_baseline_v0_70_0 import (
    build_full_registry_task_bundle,
    merge_workspace_results,
    summarize_full_registry_baseline,
    summarize_hard_candidate_repeatability,
)


class FullRegistryBaselineV070Tests(unittest.TestCase):
    def test_build_full_registry_task_bundle_loads_source_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "case.json"
            source.write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "task_type": "repair",
                        "title": "Fix case A",
                        "description": "Repair the model.",
                        "constraints": ["Keep model name unchanged."],
                        "initial_model": "model A\nend A;\n",
                        "verification": {"check_model": True, "simulate": {"stop_time": 0.2, "intervals": 20}},
                    }
                ),
                encoding="utf-8",
            )
            registry = root / "registry.jsonl"
            registry.write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "family": "family_a",
                        "registry_status": "candidate",
                        "repeatability_status": "not_run",
                        "source_reference": str(source),
                        "known_hard_for": ["provider/model/profile"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            out = root / "out"
            summary = build_full_registry_task_bundle(registry_path=registry, out_dir=out)
            task = json.loads((out / "tasks.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(summary["task_count"], 1)
            self.assertEqual(task["case_id"], "case_a")
            self.assertEqual(task["dataset_split"], "holdout")
            self.assertEqual(task["registry_bundle"], "v0.70_full_registry")
            self.assertEqual(task["registry_family"], "family_a")
            self.assertEqual(task["verification"]["simulate"]["intervals"], 20)
            self.assertEqual(task["known_hard_for"], ["provider/model/profile"])

    def test_summarize_full_registry_baseline_keeps_not_run_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry.jsonl"
            registry.write_text(
                "\n".join(
                    [
                        json.dumps({"case_id": "pass_case", "family": "f1"}),
                        json.dumps({"case_id": "fail_case", "family": "f1"}),
                        json.dumps({"case_id": "missing_case", "family": "f2"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            results = root / "results.jsonl"
            results.write_text(
                "\n".join(
                    [
                        json.dumps({"case_id": "pass_case", "final_verdict": "PASS", "candidate_files": [{}]}),
                        json.dumps({"case_id": "fail_case", "final_verdict": "FAILED", "candidate_files": []}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = summarize_full_registry_baseline(
                registry_path=registry,
                results_path=results,
                out_dir=root / "summary",
            )
            self.assertFalse(summary["artifact_complete"])
            self.assertEqual(summary["status_counts"]["easy_or_solved"], 1)
            self.assertEqual(summary["status_counts"]["hard_candidate"], 1)
            self.assertEqual(summary["status_counts"]["not_run"], 1)
            self.assertEqual(summary["not_run_case_ids"], ["missing_case"])

    def test_summarize_full_registry_baseline_ignores_extra_result_cases_for_completeness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry.jsonl"
            registry.write_text(json.dumps({"case_id": "case_a", "family": "f1"}) + "\n", encoding="utf-8")
            results = root / "results.jsonl"
            results.write_text(
                "\n".join(
                    [
                        json.dumps({"case_id": "case_a", "final_verdict": "PASS"}),
                        json.dumps({"case_id": "extra_case", "final_verdict": "PASS"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = summarize_full_registry_baseline(
                registry_path=registry,
                results_path=results,
                out_dir=root / "summary_extra",
            )
            self.assertTrue(summary["artifact_complete"])
            self.assertEqual(summary["completed_case_count"], 1)
            self.assertEqual(summary["extra_result_case_count"], 1)

    def test_merge_workspace_results_prefers_retry_without_provider_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.jsonl"
            retry = root / "retry.jsonl"
            first.write_text(
                json.dumps({"case_id": "case_a", "final_verdict": "FAILED", "provider_error": "timeout"})
                + "\n",
                encoding="utf-8",
            )
            retry.write_text(
                json.dumps({"case_id": "case_a", "final_verdict": "PASS", "token_used": 10}) + "\n",
                encoding="utf-8",
            )
            out = root / "merged" / "results.jsonl"
            summary = merge_workspace_results(result_paths=[first, retry], out_path=out)
            rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(summary["duplicate_count"], 1)
            self.assertEqual(rows[0]["final_verdict"], "PASS")

    def test_summarize_hard_candidate_repeatability_splits_repeatable_and_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps({"hard_candidate_case_ids": ["case_hard", "case_unstable"]}),
                encoding="utf-8",
            )
            repeat = root / "repeat.jsonl"
            repeat.write_text(
                "\n".join(
                    [
                        json.dumps({"case_id": "case_hard", "final_verdict": "FAILED"}),
                        json.dumps({"case_id": "case_unstable", "final_verdict": "PASS", "submitted": True}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = summarize_hard_candidate_repeatability(
                baseline_summary_path=baseline,
                repeat_results_path=repeat,
                out_dir=root / "repeat_summary",
            )
            self.assertTrue(summary["conclusion_allowed"])
            self.assertEqual(summary["repeatable_hard_candidate_case_ids"], ["case_hard"])
            self.assertEqual(summary["unstable_case_ids"], ["case_unstable"])


if __name__ == "__main__":
    unittest.main()
