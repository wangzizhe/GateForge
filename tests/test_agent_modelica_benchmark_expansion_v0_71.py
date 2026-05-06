from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_expansion_v0_71_0 import (
    build_harder_non_connector_seed_candidates,
    build_non_connector_seed_candidates,
    build_solved_case_ease_audit,
    ease_bucket,
)


class BenchmarkExpansionV071Tests(unittest.TestCase):
    def test_ease_bucket_separates_fast_and_expensive_solved_cases(self) -> None:
        self.assertEqual(
            ease_bucket({"baseline_status": "easy_or_solved", "candidate_count": 2, "token_used": 20_000}),
            "trivial_or_low_medium",
        )
        self.assertEqual(
            ease_bucket({"baseline_status": "easy_or_solved", "candidate_count": 4, "token_used": 50_000}),
            "medium_solved",
        )
        self.assertEqual(
            ease_bucket({"baseline_status": "easy_or_solved", "candidate_count": 8, "token_used": 90_000}),
            "expensive_solved",
        )
        self.assertEqual(ease_bucket({"baseline_status": "hard_candidate"}), "not_solved")

    def test_build_solved_case_ease_audit_writes_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            difficulty = root / "difficulty.jsonl"
            difficulty.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "case_id": "case_a",
                                "family": "conditional_parameter_structure",
                                "baseline_status": "easy_or_solved",
                                "candidate_count": 2,
                                "token_used": 10_000,
                            }
                        ),
                        json.dumps(
                            {
                                "case_id": "case_b",
                                "family": "replaceable_partial_contract",
                                "baseline_status": "hard_candidate",
                                "candidate_count": 6,
                                "token_used": 96_000,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            tasks = root / "tasks.jsonl"
            tasks.write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "title": "Fix conditional parameter branch",
                        "description": "A parameter branch is incomplete.",
                        "constraints": [],
                        "initial_model": "model A\n  parameter Boolean useA=true;\nequation\nend A;",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            summary = build_solved_case_ease_audit(
                difficulty_path=difficulty,
                tasks_path=tasks,
                out_dir=root / "out",
            )
            self.assertEqual(summary["solved_case_count"], 1)
            self.assertEqual(summary["not_solved_case_count"], 1)
            self.assertIn("conditional_parameter_structure", summary["next_family_targets"])
            self.assertTrue((root / "out" / "case_ease_audit.jsonl").exists())

    def test_build_non_connector_seed_candidates_covers_target_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_non_connector_seed_candidates(out_dir=Path(tmp) / "seeds")
            self.assertEqual(summary["task_count"], 8)
            self.assertEqual(summary["family_counts"]["conditional_parameter_structure"], 2)
            self.assertEqual(summary["family_counts"]["replaceable_partial_contract"], 2)
            self.assertEqual(summary["family_counts"]["reusable_contract_adapter"], 2)
            self.assertEqual(summary["family_counts"]["general_model_check_structural"], 2)
            tasks_path = Path(summary["tasks_path"])
            rows = [json.loads(line) for line in tasks_path.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(all(row["dataset_split"] == "holdout" for row in rows))
            self.assertTrue(all("root cause" not in row["description"].lower() for row in rows))

    def test_build_harder_non_connector_seed_candidates_uses_broader_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_harder_non_connector_seed_candidates(out_dir=Path(tmp) / "harder")
            self.assertEqual(summary["task_count"], 4)
            self.assertEqual(set(summary["family_counts"]), {
                "conditional_parameter_structure",
                "replaceable_partial_contract",
                "reusable_contract_adapter",
                "general_model_check_structural",
            })
            rows = [
                json.loads(line)
                for line in Path(summary["tasks_path"]).read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(all(row["registry_bundle"] == "v0.71_non_connector_candidates" for row in rows))
            self.assertTrue(any("array" in row["description"].lower() for row in rows))


if __name__ == "__main__":
    unittest.main()
