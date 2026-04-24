from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_distribution_reaudit_v0_21_3 import (
    build_distribution_reaudit,
    normalize_counts,
    run_distribution_reaudit,
)


def _generation_summary() -> dict:
    return {
        "generation_failure_distribution_p": {
            "ET01": 0.5,
            "ET02": 0.25,
            "ET07": 0.25,
        }
    }


def _taxonomy_summary() -> dict:
    return {"bucket_counts": {"ET07": 2, "ET08": 2}}


def _family_candidate(bucket_id: str) -> dict:
    return {"family_candidate_id": f"v0211_{bucket_id}", "bucket_id": bucket_id}


class DistributionReauditV0213Tests(unittest.TestCase):
    def test_normalize_counts_converts_counts_to_distribution(self) -> None:
        self.assertEqual(normalize_counts({"ET01": 1, "ET02": 3}), {"ET01": 0.25, "ET02": 0.75})

    def test_build_distribution_reaudit_keeps_actual_unchanged_when_no_main_admission(self) -> None:
        summary = build_distribution_reaudit(
            generation_summary=_generation_summary(),
            taxonomy_summary=_taxonomy_summary(),
            family_candidates=[_family_candidate("ET01"), _family_candidate("ET02")],
            admission_audit={"main_admissible_count": 0, "blocked_from_main_benchmark_count": 2},
        )

        self.assertEqual(summary["actual_distance"], summary["actual_plus_admitted_distance"])
        self.assertLess(summary["isolated_projection_distance"], summary["actual_distance"])
        self.assertEqual(summary["next_action"], "source_pairing_and_omc_validation_before_distribution_claim")

    def test_build_distribution_reaudit_includes_admitted_when_present(self) -> None:
        summary = build_distribution_reaudit(
            generation_summary=_generation_summary(),
            taxonomy_summary=_taxonomy_summary(),
            family_candidates=[_family_candidate("ET01"), _family_candidate("ET02")],
            admission_audit={"main_admissible_count": 2, "blocked_from_main_benchmark_count": 0},
        )

        self.assertLess(summary["actual_plus_admitted_distance"], summary["actual_distance"])

    def test_run_distribution_reaudit_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generation_path = root / "generation.json"
            taxonomy_path = root / "taxonomy.json"
            family_path = root / "family.jsonl"
            audit_path = root / "audit.json"
            out_dir = root / "out"
            generation_path.write_text(json.dumps(_generation_summary()), encoding="utf-8")
            taxonomy_path.write_text(json.dumps(_taxonomy_summary()), encoding="utf-8")
            family_path.write_text(
                "\n".join([json.dumps(_family_candidate("ET01")), json.dumps(_family_candidate("ET02"))]),
                encoding="utf-8",
            )
            audit_path.write_text(
                json.dumps({"main_admissible_count": 0, "blocked_from_main_benchmark_count": 2}),
                encoding="utf-8",
            )

            summary = run_distribution_reaudit(
                generation_summary_path=generation_path,
                taxonomy_summary_path=taxonomy_path,
                family_candidate_path=family_path,
                admission_audit_path=audit_path,
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
