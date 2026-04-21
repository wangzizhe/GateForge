from __future__ import annotations

import unittest

from scripts.run_raw_only_underdetermined_trajectory_v0_19_42 import (
    _build_summary,
    _classify_turn_shape,
    _filter_families,
)


class TestV01942RawOnlyTrajectory(unittest.TestCase):
    def test_classify_single_fix_closure(self) -> None:
        attempts = [
            {
                "round": 1,
                "patched_text_present": True,
                "model_changed": True,
                "check_pass_before_patch": False,
                "check_pass_after_patch": True,
                "omc_output_before_patch": "err a",
            }
        ]
        self.assertEqual(_classify_turn_shape(attempts, True), "single_fix_closure")

    def test_classify_partial_fix_then_continue(self) -> None:
        attempts = [
            {
                "round": 1,
                "patched_text_present": True,
                "model_changed": True,
                "check_pass_before_patch": False,
                "check_pass_after_patch": False,
                "omc_output_before_patch": "Variable a missing",
            },
            {
                "round": 2,
                "patched_text_present": True,
                "model_changed": True,
                "check_pass_before_patch": False,
                "check_pass_after_patch": True,
                "omc_output_before_patch": "Variable b missing",
            },
        ]
        self.assertEqual(_classify_turn_shape(attempts, True), "partial_fix_then_continue")

    def test_classify_wrong_direction_then_recover(self) -> None:
        attempts = [
            {
                "round": 1,
                "patched_text_present": True,
                "model_changed": True,
                "check_pass_before_patch": False,
                "check_pass_after_patch": False,
                "omc_output_before_patch": "Variable a missing",
            },
            {
                "round": 2,
                "patched_text_present": True,
                "model_changed": True,
                "check_pass_before_patch": False,
                "check_pass_after_patch": True,
                "omc_output_before_patch": "Variable a missing",
            },
        ]
        self.assertEqual(_classify_turn_shape(attempts, True), "wrong_direction_then_recover")

    def test_classify_stalled_no_progress(self) -> None:
        attempts = [
            {
                "round": 1,
                "patched_text_present": True,
                "model_changed": False,
                "llm_error_class": "",
                "check_pass_before_patch": False,
                "check_pass_after_patch": False,
                "omc_output_before_patch": "Variable a missing",
            }
        ]
        self.assertEqual(_classify_turn_shape(attempts, False), "stalled_no_progress")

    def test_classify_service_fail(self) -> None:
        attempts = [
            {
                "round": 1,
                "patched_text_present": False,
                "model_changed": False,
                "llm_error_class": "service_error",
                "check_pass_before_patch": False,
                "check_pass_after_patch": None,
                "omc_output_before_patch": "docker denied",
            }
        ]
        self.assertEqual(_classify_turn_shape(attempts, False), "format_or_service_fail")

    def test_build_summary_groups_by_family(self) -> None:
        rows = [
            {"family": "parameter_promotion", "final_status": "PASS", "turn_count": 2, "turn_shape": "single_fix_closure"},
            {"family": "parameter_promotion", "final_status": "FAIL", "turn_count": 3, "turn_shape": "format_or_service_fail"},
            {"family": "phantom_variable", "final_status": "PASS", "turn_count": 3, "turn_shape": "partial_fix_then_continue"},
        ]
        summary = _build_summary(rows)
        self.assertEqual(summary["overall"]["n_cases"], 3)
        self.assertEqual(summary["families"]["parameter_promotion"]["n_cases"], 2)
        self.assertEqual(summary["families"]["parameter_promotion"]["pass_rate"], 0.5)
        self.assertEqual(summary["families"]["parameter_promotion"]["clean_n"], 1)
        self.assertEqual(summary["families"]["parameter_promotion"]["clean_pass_rate"], 1.0)
        self.assertEqual(summary["families"]["phantom_variable"]["turn_shapes"]["partial_fix_then_continue"], 1)

    def test_filter_families(self) -> None:
        cases = [
            {"_family": "parameter_promotion", "candidate_id": "a"},
            {"_family": "phantom_variable", "candidate_id": "b"},
        ]
        filtered = _filter_families(cases, ["phantom_variable"])
        self.assertEqual([row["candidate_id"] for row in filtered], ["b"])


if __name__ == "__main__":
    unittest.main()
