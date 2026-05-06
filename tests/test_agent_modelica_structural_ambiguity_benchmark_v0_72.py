from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_structural_ambiguity_benchmark_v0_72_0 import (
    build_structural_ambiguity_seed_candidates,
    build_structural_ambiguity_variants,
    summarize_budget_calibration,
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


if __name__ == "__main__":
    unittest.main()
