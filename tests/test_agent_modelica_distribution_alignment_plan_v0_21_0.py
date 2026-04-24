from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_distribution_alignment_plan_v0_21_0 import (
    build_alignment_plan,
    build_gap_plan,
    load_jsonl,
    run_distribution_alignment_plan,
    total_variation_distance,
)


def _generation_summary() -> dict:
    return {
        "generation_failure_distribution_p": {
            "ET01": 0.5,
            "ET02": 0.25,
            "ET03": 0.125,
            "ET07": 0.125,
        },
        "mutation_distribution_q": {
            "ET06": 0.5,
            "ET07": 0.5,
        },
    }


def _taxonomy_summary() -> dict:
    return {"bucket_counts": {"ET06": 2, "ET07": 2}}


def _candidate(bucket_id: str, candidate_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "bucket_id": bucket_id,
        "benchmark_admission_status": "admitted",
    }


class DistributionAlignmentPlanV0210Tests(unittest.TestCase):
    def test_total_variation_distance_uses_union_of_buckets(self) -> None:
        distance = total_variation_distance({"ET01": 0.5, "ET02": 0.5}, {"ET02": 0.25, "ET03": 0.75})

        self.assertEqual(distance, 0.75)

    def test_build_gap_plan_prioritizes_generation_gap_buckets(self) -> None:
        plan = build_gap_plan(
            p_dist={"ET01": 0.5, "ET02": 0.25, "ET03": 0.125},
            q_dist={"ET07": 1.0},
            candidate_counts={"ET01": 2, "ET02": 1, "ET03": 1},
        )

        self.assertEqual([row["bucket_id"] for row in plan], ["ET01", "ET02", "ET03"])
        self.assertEqual(plan[0]["candidate_family"], "generation_parse_load_failure")
        self.assertEqual(plan[0]["priority"], "high")

    def test_build_alignment_plan_reports_ready_when_all_targets_have_candidates(self) -> None:
        summary = build_alignment_plan(
            generation_summary=_generation_summary(),
            taxonomy_summary=_taxonomy_summary(),
            candidates=[
                _candidate("ET01", "a"),
                _candidate("ET02", "b"),
                _candidate("ET03", "c"),
                _candidate("ET07", "d"),
            ],
        )

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["target_isolated_candidate_count"], 3)
        self.assertEqual(summary["default_benchmark_admission"], "isolated_pool_only")
        self.assertEqual(summary["next_version"], "v0.21.1")

    def test_build_alignment_plan_marks_missing_target_for_review(self) -> None:
        summary = build_alignment_plan(
            generation_summary=_generation_summary(),
            taxonomy_summary=_taxonomy_summary(),
            candidates=[_candidate("ET01", "a"), _candidate("ET02", "b")],
        )

        self.assertEqual(summary["status"], "REVIEW")
        self.assertIn("ET03", summary["missing_or_unready_target_buckets"])

    def test_load_jsonl_ignores_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text(json.dumps({"bucket_id": "ET01"}) + "\n\n", encoding="utf-8")

            rows = load_jsonl(path)

        self.assertEqual(rows, [{"bucket_id": "ET01"}])

    def test_run_distribution_alignment_plan_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generation_path = root / "generation.json"
            taxonomy_path = root / "taxonomy.json"
            candidate_path = root / "candidates.jsonl"
            out_dir = root / "out"
            generation_path.write_text(json.dumps(_generation_summary()), encoding="utf-8")
            taxonomy_path.write_text(json.dumps(_taxonomy_summary()), encoding="utf-8")
            candidate_path.write_text(
                "\n".join(
                    [
                        json.dumps(_candidate("ET01", "a")),
                        json.dumps(_candidate("ET02", "b")),
                        json.dumps(_candidate("ET03", "c")),
                    ]
                ),
                encoding="utf-8",
            )

            summary = run_distribution_alignment_plan(
                generation_summary_path=generation_path,
                taxonomy_summary_path=taxonomy_path,
                candidate_path=candidate_path,
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
