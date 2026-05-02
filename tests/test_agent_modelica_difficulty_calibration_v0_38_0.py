from __future__ import annotations

import unittest

from gateforge.agent_modelica_difficulty_calibration_v0_38_0 import (
    build_difficulty_calibration_summary,
    classify_seed_difficulty,
)


def _seed(**updates: object) -> dict:
    seed = {
        "case_id": "sem_19",
        "family": "arrayed_connector_flow",
        "known_hard_for": ["provider / model / base / 32k / run1", "provider / model / base / 32k / run2"],
        "registry_status": "repeatable_candidate",
        "admission_status": "admitted_via_live_failure",
        "repeatability_status": "repeatable",
    }
    seed.update(updates)
    return seed


class DifficultyCalibrationV0380Tests(unittest.TestCase):
    def test_repeatable_known_hard_becomes_hard_negative(self) -> None:
        row = classify_seed_difficulty(
            _seed(),
            gate_row={"case_id": "sem_19", "formal_benchmark_eligible": True, "blockers": [], "status": "PASS"},
        )
        self.assertEqual(row["difficulty_bucket"], "hard_negative")

    def test_known_hard_without_repeatability_is_prior_only(self) -> None:
        row = classify_seed_difficulty(
            _seed(repeatability_status="repeatability_pending"),
            gate_row={"case_id": "sem_19", "formal_benchmark_eligible": False, "blockers": [], "status": "PASS"},
        )
        self.assertEqual(row["difficulty_bucket"], "known_hard_prior")

    def test_mixed_pass_fail_becomes_unstable(self) -> None:
        row = classify_seed_difficulty(
            _seed(),
            gate_row={"case_id": "sem_19", "formal_benchmark_eligible": True, "blockers": [], "status": "PASS"},
            pass_count=1,
            fail_count=1,
        )
        self.assertEqual(row["difficulty_bucket"], "unstable")

    def test_pass_only_becomes_easy(self) -> None:
        row = classify_seed_difficulty(
            _seed(known_hard_for=[]),
            gate_row={"case_id": "sem_19", "formal_benchmark_eligible": True, "blockers": [], "status": "PASS"},
            pass_count=2,
            fail_count=0,
        )
        self.assertEqual(row["difficulty_bucket"], "easy")

    def test_repeated_fail_becomes_hard_negative(self) -> None:
        row = classify_seed_difficulty(
            _seed(known_hard_for=[], repeatability_status="repeatability_pending"),
            gate_row={"case_id": "sem_19", "formal_benchmark_eligible": False, "blockers": [], "status": "PASS"},
            pass_count=0,
            fail_count=2,
        )
        self.assertEqual(row["difficulty_bucket"], "hard_negative")

    def test_prompt_leakage_becomes_invalid(self) -> None:
        row = classify_seed_difficulty(
            _seed(),
            gate_row={"case_id": "sem_19", "formal_benchmark_eligible": False, "blockers": ["prompt_leakage"], "status": "REVIEW"},
        )
        self.assertEqual(row["difficulty_bucket"], "invalid")

    def test_summary_counts_buckets(self) -> None:
        summary = build_difficulty_calibration_summary(
            [_seed(), _seed(case_id="sem_20", repeatability_status="repeatability_pending")],
            gate_rows=[
                {"case_id": "sem_19", "formal_benchmark_eligible": True, "blockers": [], "status": "PASS"},
                {"case_id": "sem_20", "formal_benchmark_eligible": False, "blockers": [], "status": "PASS"},
            ],
        )
        self.assertEqual(summary["bucket_counts"]["hard_negative"], 1)
        self.assertEqual(summary["bucket_counts"]["known_hard_prior"], 1)
        self.assertEqual(summary["formal_hard_negative_case_ids"], ["sem_19"])


if __name__ == "__main__":
    unittest.main()
