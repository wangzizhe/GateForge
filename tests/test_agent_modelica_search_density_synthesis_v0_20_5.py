from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_search_density_synthesis_v0_20_5 import (
    build_search_density_decisions,
    build_search_density_synthesis,
)


class SearchDensitySynthesisV0205Tests(unittest.TestCase):
    def test_build_decisions_prioritizes_diversity_profile(self) -> None:
        decisions = build_search_density_decisions(
            {
                "adaptive_budget": {"promotion_recommendation": "eligible_for_live_arm"},
                "beam_width_2": {"promotion_recommendation": "do_not_promote_without_selector_revision"},
                "beam_width_4": {"promotion_recommendation": "eligible_for_live_tree_search_arm"},
                "candidate_diversity": {"recommendation": "prioritize_diversity_prompting"},
                "diversity_resampling": {"conclusion": "diversity_aware_resampling_profile_ready"},
            }
        )

        self.assertEqual(decisions["default_strategy"], "fixed-c5-remains-current-default")
        self.assertEqual(decisions["adaptive_budget"]["decision"], "live_arm_candidate")
        self.assertEqual(decisions["beam_tree_search"]["decision"], "beam_width_4_live_arm_candidate")
        self.assertEqual(decisions["diversity_aware_resampling"]["decision"], "highest_priority_live_profile")

    def test_build_search_density_synthesis_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {
                "substrate": root / "substrate.json",
                "adaptive_budget": root / "adaptive.json",
                "beam_width_2": root / "beam2.json",
                "beam_width_3": root / "beam3.json",
                "beam_width_4": root / "beam4.json",
                "candidate_diversity": root / "diversity.json",
                "diversity_resampling": root / "resampling.json",
            }
            payloads = {
                "substrate": {"status": "PASS", "main_case_count": 48, "shadow_case_count": 12},
                "adaptive_budget": {
                    "status": "PASS",
                    "promotion_recommendation": "eligible_for_live_arm",
                    "candidate_savings_rate": 0.16,
                    "simulate_round_retention_rate": 0.8,
                },
                "beam_width_2": {
                    "status": "PASS",
                    "promotion_recommendation": "do_not_promote_without_selector_revision",
                    "simulate_node_retention_rate": 0.47,
                },
                "beam_width_3": {"status": "PASS"},
                "beam_width_4": {
                    "status": "PASS",
                    "promotion_recommendation": "eligible_for_live_tree_search_arm",
                    "simulate_node_retention_rate": 0.88,
                },
                "candidate_diversity": {
                    "status": "PASS",
                    "recommendation": "prioritize_diversity_prompting",
                    "average_structural_uniqueness_rate": 0.34,
                },
                "diversity_resampling": {
                    "status": "PASS",
                    "conclusion": "diversity_aware_resampling_profile_ready",
                    "diversity_resample_rate": 1.0,
                },
            }
            for name, path in inputs.items():
                path.write_text(json.dumps(payloads[name]), encoding="utf-8")

            out_dir = root / "out"
            summary = build_search_density_synthesis(input_paths=inputs, out_dir=out_dir)

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertEqual(summary["conclusion"], "search_density_v2_offline_phase_closed")


if __name__ == "__main__":
    unittest.main()
