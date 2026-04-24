from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_search_density_v0_20_0 import (
    BASELINE_ARMS,
    METRIC_SCHEMA,
    build_broadened_repair_set,
    build_search_density_substrate,
    build_shadow_generation_set,
    normalize_case,
    summarize_substrate,
)


class SearchDensityV0200Tests(unittest.TestCase):
    def test_normalize_case_preserves_public_fields(self) -> None:
        row = {
            "candidate_id": "case_a",
            "mutation_family": "under",
            "failure_type": "constraint",
            "expected_stage": "simulate",
            "difficulty_prior": "hard",
            "workflow_goal": "Repair model.",
        }

        normalized = normalize_case(row, set_name="broadened_repair")

        self.assertEqual(normalized["candidate_id"], "case_a")
        self.assertEqual(normalized["benchmark_family"], "under")
        self.assertEqual(normalized["failure_type"], "constraint")
        self.assertEqual(normalized["difficulty_hint"], "hard")
        self.assertTrue(normalized["workflow_goal_present"])

    def test_broadened_builder_deduplicates_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "admitted_cases.jsonl"
            rows = [
                {"candidate_id": "case_a", "mutation_family": "family_a"},
                {"candidate_id": "case_a", "mutation_family": "family_a"},
                {"candidate_id": "case_b", "mutation_family": "family_b"},
            ]
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            built = build_broadened_repair_set(
                sources=[{"path": path, "difficulty_hint": "easy", "max_cases": 3}],
                target_max_cases=10,
            )

        self.assertEqual([row["candidate_id"] for row in built], ["case_a", "case_b"])

    def test_shadow_generation_set_is_shadow_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidates.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "candidate_id": "shadow_a",
                        "bucket_id": "ET01",
                        "difficulty": "T1",
                        "proposed_mutation_family": "parse_failure",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            built = build_shadow_generation_set(path)

        self.assertEqual(len(built), 1)
        self.assertEqual(built[0]["scoring_role"], "shadow_only")
        self.assertEqual(built[0]["bucket_id"], "ET01")

    def test_summary_reports_required_metrics_and_baselines(self) -> None:
        case_sets = {
            "continuity": [
                {"scoring_role": "main", "difficulty_hint": "hard", "benchmark_family": "a"}
                for _ in range(8)
            ],
            "broadened_repair": [
                {"scoring_role": "main", "difficulty_hint": "medium", "benchmark_family": "b"}
                for _ in range(20)
            ],
            "shadow_generation_derived": [
                {"scoring_role": "shadow_only", "difficulty_hint": "T1", "benchmark_family": "c"}
            ],
        }

        summary = summarize_substrate(case_sets)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["main_case_count"], 28)
        self.assertEqual(summary["shadow_case_count"], 1)
        self.assertEqual(summary["metric_schema"], METRIC_SCHEMA)
        self.assertEqual(summary["baseline_arms"], BASELINE_ARMS)

    def test_build_search_density_substrate_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            substrate = build_search_density_substrate(out_dir=out_dir, broadened_target_max_cases=20)

            self.assertTrue((out_dir / "substrate.json").exists())
            self.assertTrue((out_dir / "summary.json").exists())

        summary = substrate["summary"]
        self.assertEqual(summary["version"], "v0.20.0")
        self.assertIn(summary["status"], {"PASS", "INCOMPLETE"})
        self.assertIn("continuity", summary["set_counts"])


if __name__ == "__main__":
    unittest.main()
