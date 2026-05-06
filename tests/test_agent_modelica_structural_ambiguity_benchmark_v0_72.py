from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_structural_ambiguity_benchmark_v0_72_0 import (
    build_second_generation_structural_ambiguity_variants,
    build_medium_hard_pack,
    build_residual_closure_expansion_variants,
    build_shifted_closure_expansion_variants,
    build_structural_ambiguity_seed_candidates,
    build_structural_ambiguity_variants,
    build_stable_pattern_expansion_variants,
    summarize_budget_calibration,
    summarize_budget_repeatability,
)


class StructuralAmbiguityBenchmarkV072Tests(unittest.TestCase):
    def test_build_structural_ambiguity_seed_candidates_covers_target_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_structural_ambiguity_seed_candidates(out_dir=Path(tmp) / "tasks")
            self.assertEqual(summary["task_count"], 6)
            self.assertEqual(summary["family_counts"]["balanced_structural_singularity"], 2)
            self.assertEqual(summary["family_counts"]["mixed_over_under_constraint"], 2)
            self.assertEqual(summary["family_counts"]["redeclare_contract_boundary"], 2)
            rows = [
                json.loads(line)
                for line in Path(summary["tasks_path"]).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(all(row["dataset_split"] == "holdout" for row in rows))
            self.assertTrue(all(row["registry_bundle"] == "v0.72_structural_ambiguity_candidates" for row in rows))
            prompt_text = "\n".join(row["description"] for row in rows).lower()
            self.assertNotIn("correct fix", prompt_text)
            self.assertNotIn("root cause", prompt_text)

    def test_build_structural_ambiguity_variants_extends_budget_sensitive_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_structural_ambiguity_variants(out_dir=Path(tmp) / "variants")
            self.assertEqual(summary["task_count"], 4)
            self.assertEqual(summary["family_counts"]["balanced_structural_singularity"], 2)
            self.assertEqual(summary["family_counts"]["mixed_over_under_constraint"], 2)
            rows = [
                json.loads(line)
                for line in Path(summary["tasks_path"]).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(all(row["registry_bundle"] == "v0.72_structural_ambiguity_candidates" for row in rows))
            self.assertTrue(any("rank loss" in row["title"].lower() for row in rows))

    def test_build_second_generation_structural_ambiguity_variants_targets_projection_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_second_generation_structural_ambiguity_variants(out_dir=Path(tmp) / "second")
            self.assertEqual(summary["task_count"], 4)
            self.assertEqual(summary["family_counts"]["projection_closure_rank_loss"], 2)
            self.assertEqual(summary["family_counts"]["residual_projection_closure_conflict"], 2)
            rows = [
                json.loads(line)
                for line in Path(summary["tasks_path"]).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(all("closure" in row["registry_family"] for row in rows))
            self.assertTrue(all("correct fix" not in row["description"].lower() for row in rows))

    def test_summarize_budget_calibration_detects_budget_sensitive_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            low = root / "low.jsonl"
            high = root / "high.jsonl"
            low.write_text(
                json.dumps({"case_id": "case_a", "final_verdict": "FAILED", "candidate_files": []}) + "\n",
                encoding="utf-8",
            )
            high.write_text(
                json.dumps({"case_id": "case_a", "final_verdict": "PASS", "submitted": True, "candidate_files": [{}]})
                + "\n",
                encoding="utf-8",
            )
            summary = summarize_budget_calibration(
                result_paths_by_budget={"48k": low, "96k": high},
                out_dir=root / "summary",
            )
            self.assertEqual(summary["budget_sensitive_case_ids"], ["case_a"])
            self.assertEqual(summary["calibration_status_counts"]["budget_sensitive_medium_hard"], 1)

    def test_summarize_budget_repeatability_marks_same_budget_pass_fail_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            low_a = root / "low_a.jsonl"
            low_b = root / "low_b.jsonl"
            high = root / "high.jsonl"
            low_a.write_text(json.dumps({"case_id": "case_a", "final_verdict": "FAILED"}) + "\n", encoding="utf-8")
            low_b.write_text(json.dumps({"case_id": "case_a", "final_verdict": "PASS"}) + "\n", encoding="utf-8")
            high.write_text(json.dumps({"case_id": "case_a", "final_verdict": "PASS"}) + "\n", encoding="utf-8")
            summary = summarize_budget_repeatability(
                result_paths_by_run={"32k_initial": low_a, "32k_repeat": low_b, "64k": high},
                out_dir=root / "repeatability",
            )
            self.assertEqual(summary["unstable_case_ids"], ["case_a"])
            self.assertEqual(summary["repeatability_status_counts"]["unstable_medium_candidate"], 1)

    def test_build_medium_hard_pack_excludes_unstable_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            tasks.write_text(
                "\n".join(
                    [
                        json.dumps({"case_id": "stable_case", "registry_family": "f"}),
                        json.dumps({"case_id": "unstable_case", "registry_family": "f"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            repeatability = root / "repeatability.json"
            repeatability.write_text(
                json.dumps(
                    {
                        "repeatable_budget_sensitive_case_ids": ["stable_case"],
                        "unstable_case_ids": ["unstable_case"],
                    }
                ),
                encoding="utf-8",
            )
            summary = build_medium_hard_pack(
                task_paths=[tasks],
                repeatability_summary_paths=[repeatability],
                out_dir=root / "pack",
            )
            self.assertEqual(summary["medium_hard_case_ids"], ["stable_case"])
            self.assertEqual(summary["unstable_case_ids"], ["unstable_case"])
            self.assertTrue(summary["conclusion_allowed"])

    def test_build_stable_pattern_expansion_variants_extends_strict_medium_hard_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_stable_pattern_expansion_variants(out_dir=Path(tmp) / "expansion")
            self.assertEqual(summary["task_count"], 6)
            self.assertEqual(summary["family_counts"]["mixed_over_under_constraint"], 3)
            self.assertEqual(summary["family_counts"]["residual_projection_closure_conflict"], 3)
            rows = [
                json.loads(line)
                for line in Path(summary["tasks_path"]).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(
                all(row["registry_bundle"] == "v0.76_structural_ambiguity_stable_pattern_expansion" for row in rows)
            )
            prompt_text = "\n".join(row["description"] for row in rows).lower()
            self.assertNotIn("correct fix", prompt_text)
            self.assertNotIn("root cause", prompt_text)

    def test_build_residual_closure_expansion_variants_focuses_stable_residual_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_residual_closure_expansion_variants(out_dir=Path(tmp) / "residual")
            self.assertEqual(summary["task_count"], 6)
            self.assertEqual(summary["family_counts"], {"residual_projection_closure_conflict": 6})
            rows = [
                json.loads(line)
                for line in Path(summary["tasks_path"]).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(
                all(row["registry_bundle"] == "v0.77_structural_ambiguity_residual_closure_expansion" for row in rows)
            )
            self.assertTrue(all(row["registry_family"] == "residual_projection_closure_conflict" for row in rows))
            prompt_text = "\n".join(row["description"] for row in rows).lower()
            self.assertNotIn("correct fix", prompt_text)
            self.assertNotIn("root cause", prompt_text)

    def test_build_shifted_closure_expansion_variants_focuses_shifted_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_shifted_closure_expansion_variants(out_dir=Path(tmp) / "shifted")
            self.assertEqual(summary["task_count"], 6)
            self.assertEqual(summary["family_counts"], {"residual_projection_closure_conflict": 6})
            rows = [
                json.loads(line)
                for line in Path(summary["tasks_path"]).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(
                all(row["registry_bundle"] == "v0.78_structural_ambiguity_shifted_closure_expansion" for row in rows)
            )
            self.assertEqual(summary["source_pattern_case_ids"], ["residual_projection_09_shifted_index_closure_conflict"])
            prompt_text = "\n".join(row["description"] for row in rows).lower()
            self.assertNotIn("correct fix", prompt_text)
            self.assertNotIn("root cause", prompt_text)


if __name__ == "__main__":
    unittest.main()
