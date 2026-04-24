from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_early_compile_family_v0_21_1 import (
    build_family_candidate,
    build_family_candidates,
    run_early_compile_family_builder,
    summarize_family_candidates,
)


def _candidate(bucket_id: str = "ET01", candidate_id: str = "v01961_et01_a") -> dict:
    return {
        "candidate_id": candidate_id,
        "source_task_id": "task_a",
        "bucket_id": bucket_id,
        "domain": "electrical",
        "difficulty": "T1",
        "observed_failure_excerpt": "Parser error: unexpected token",
    }


class EarlyCompileFamilyV0211Tests(unittest.TestCase):
    def test_build_family_candidate_maps_target_bucket_to_family(self) -> None:
        candidate = build_family_candidate(_candidate("ET02", "v01961_et02_a"))

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate["family_id"], "missing_component_or_library_reference")
        self.assertEqual(candidate["benchmark_admission_status"], "isolated_family_candidate_only")
        self.assertEqual(candidate["source_viability_status"], "pending_clean_source_pairing")

    def test_build_family_candidate_skips_non_target_bucket(self) -> None:
        self.assertIsNone(build_family_candidate(_candidate("ET07", "v01961_et07_a")))

    def test_build_family_candidates_deduplicates(self) -> None:
        rows = [_candidate("ET01", "same"), _candidate("ET01", "same"), _candidate("ET03", "other")]

        candidates = build_family_candidates(rows)

        self.assertEqual([row["family_candidate_id"] for row in candidates], ["v0211_same", "v0211_other"])

    def test_summarize_family_candidates_requires_all_target_buckets(self) -> None:
        candidates = build_family_candidates(
            [
                _candidate("ET01", "a"),
                _candidate("ET02", "b"),
                _candidate("ET03", "c"),
            ]
        )

        summary = summarize_family_candidates(plan_summary={"status": "PASS"}, candidates=candidates)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["family_candidate_count"], 3)
        self.assertEqual(summary["next_version"], "v0.21.2")

    def test_summarize_family_candidates_marks_missing_bucket_for_review(self) -> None:
        candidates = build_family_candidates([_candidate("ET01", "a")])

        summary = summarize_family_candidates(plan_summary={"status": "PASS"}, candidates=candidates)

        self.assertEqual(summary["status"], "REVIEW")
        self.assertIn("ET02", summary["missing_target_buckets"])

    def test_run_early_compile_family_builder_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "plan.json"
            candidate_path = root / "candidates.jsonl"
            out_dir = root / "out"
            plan_path.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
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

            summary = run_early_compile_family_builder(
                plan_path=plan_path,
                candidate_path=candidate_path,
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "family_candidates.jsonl").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
