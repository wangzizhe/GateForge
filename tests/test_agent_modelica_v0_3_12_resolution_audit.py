from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_12_resolution_audit import (
    build_v0_3_12_overall_interpretation,
)


class AgentModelicaV0312ResolutionAuditTests(unittest.TestCase):
    def test_marks_deterministic_tracks_and_planner_sensitive_reference(self) -> None:
        payload = build_v0_3_12_overall_interpretation(
            [
                {
                    "lane_id": "track_a",
                    "status": "PASS",
                    "success_resolution_path_pct": {"deterministic_rule_only": 100.0},
                    "all_resolution_path_counts": {"deterministic_rule_only": 32},
                },
                {
                    "lane_id": "track_b",
                    "status": "PASS",
                    "success_resolution_path_pct": {"deterministic_rule_only": 100.0},
                    "all_resolution_path_counts": {"deterministic_rule_only": 18},
                },
                {
                    "lane_id": "harder_holdout",
                    "status": "PASS",
                    "success_resolution_path_pct": {"deterministic_rule_only": 100.0},
                    "all_resolution_path_counts": {"deterministic_rule_only": 4, "unresolved": 1},
                },
                {
                    "lane_id": "planner_sensitive",
                    "status": "PASS",
                    "success_resolution_path_pct": {"llm_planner_assisted": 100.0},
                    "all_resolution_path_counts": {"llm_planner_assisted": 6},
                },
            ]
        )

        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["paper_claim_status"], "planner_value_visible_only_on_calibration_lane")
        self.assertEqual(
            payload["paper_claim_recommendation"],
            "treat_harder_holdout_as_failure_sidecar_and_design_new_track_c_slice",
        )
        self.assertIn("track_a", payload["deterministic_dominated_lanes"])
        self.assertIn("track_b", payload["deterministic_dominated_lanes"])
        self.assertIn("planner_sensitive", payload["planner_expressive_lanes"])
        self.assertIn("harder_holdout", payload["unresolved_lanes"])

    def test_needs_rerun_when_lane_status_is_not_pass(self) -> None:
        payload = build_v0_3_12_overall_interpretation(
            [
                {
                    "lane_id": "track_a",
                    "status": "MISSING_OR_UNSUPPORTED",
                    "success_resolution_path_pct": {},
                    "all_resolution_path_counts": {},
                }
            ]
        )

        self.assertEqual(payload["status"], "NEEDS_RERUN")
        self.assertEqual(payload["attribution_gap_lanes"], ["track_a"])


if __name__ == "__main__":
    unittest.main()
