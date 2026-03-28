from __future__ import annotations

import unittest

from gateforge.agent_modelica_layer4_family_spec_v1 import build_summary


class AgentModelicaLayer4FamilySpecV1Tests(unittest.TestCase):
    def test_build_summary_passes_with_all_required_families(self) -> None:
        summary = build_summary(
            {
                "families": [
                    {
                        "family_id": "initialization_singularity",
                        "expected_layer_hint": "layer_4",
                        "viability_status": "approved_v0_3_0",
                        "enabled_for_v0_3_0": True,
                        "mutation_acceptance_constraints": ["c1"],
                        "validation_criterion": {"min_observed_layer4_share_pct": 60.0},
                    },
                    {
                        "family_id": "structural_singularity",
                        "expected_layer_hint": "layer_4",
                        "viability_status": "deferred_v0_3_1",
                        "enabled_for_v0_3_0": False,
                        "mutation_acceptance_constraints": ["c1"],
                        "validation_criterion": {"min_stage4_stage5_share_pct": 40.0},
                    },
                    {
                        "family_id": "runtime_numerical_instability",
                        "expected_layer_hint": "layer_4",
                        "viability_status": "approved_v0_3_0",
                        "enabled_for_v0_3_0": True,
                        "mutation_acceptance_constraints": ["c1"],
                        "validation_criterion": {"min_stage4_stage5_share_pct": 50.0},
                    },
                    {
                        "family_id": "hard_multiround_simulate_failure",
                        "expected_layer_hint": "layer_4",
                        "viability_status": "approved_v0_3_0",
                        "enabled_for_v0_3_0": True,
                        "mutation_acceptance_constraints": ["c1"],
                        "validation_criterion": {"min_hard_case_rate_pct": 40.0},
                    },
                ]
            }
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["structural_singularity_viability"], "deferred_v0_3_1")

    def test_build_summary_fails_when_required_family_missing(self) -> None:
        summary = build_summary(
            {
                "families": [
                    {
                        "family_id": "initialization_singularity",
                        "expected_layer_hint": "layer_4",
                        "viability_status": "approved_v0_3_0",
                        "enabled_for_v0_3_0": True,
                        "mutation_acceptance_constraints": ["c1"],
                        "validation_criterion": {"min_observed_layer4_share_pct": 60.0},
                    }
                ]
            }
        )
        self.assertEqual(summary["status"], "FAIL")
        self.assertIn("required_family_missing", summary["reasons"])


if __name__ == "__main__":
    unittest.main()
