from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_benchmark_gf_v1 import (  # noqa: E402
    FAMILY_COMPOUND2,
    FAMILY_COMPOUND3,
    FAMILY_COMPOUND4,
    _normalise_compound,
)


class V01921CompoundBenchmarkIntegrationTests(unittest.TestCase):
    def test_normalise_compound_two_layer_sets_family_and_depth(self) -> None:
        row = {
            "candidate_id": "v01918_compound_demo",
            "source_model_path": "/tmp/source.mo",
            "mutated_model_path": "/tmp/mutated.mo",
            "workflow_goal": "goal",
            "failure_type": "behavioral_contract_fail",
            "mutation_family": "compound_underdetermined_plus_semantic",
            "compound_mutation_bugs": ["missing_ground_connects", "wrong_capacitor_value"],
            "semantic_oracle": {"kind": "simulation_based_time_constant"},
        }

        normalized = _normalise_compound(row, depth=2)

        self.assertEqual(normalized["benchmark_family"], FAMILY_COMPOUND2)
        self.assertEqual(normalized["error_layer"], 2)
        self.assertEqual(normalized["mutation_mechanism"], "compound_missing_ground_plus_wrong_capacitance")
        self.assertEqual(normalized["_compound_depth"], 2)
        self.assertEqual(normalized["_source_version"], "v0.19.18")

    def test_normalise_compound_three_layer_preserves_parameter_mutations(self) -> None:
        row = {
            "candidate_id": "v01919_triple_demo",
            "source_model_path": "/tmp/source.mo",
            "mutated_model_path": "/tmp/mutated.mo",
            "workflow_goal": "goal",
            "failure_type": "behavioral_contract_fail",
            "mutation_family": "triple_underdetermined_plus_two_semantic",
            "compound_mutation_bugs": [
                "missing_ground_connects",
                "wrong_capacitor_value",
                "wrong_resistance_value",
            ],
            "parameter_mutations": {"R_charge": {"correct": 1.0, "wrong": 2.0}},
        }

        normalized = _normalise_compound(row, depth=3)

        self.assertEqual(normalized["benchmark_family"], FAMILY_COMPOUND3)
        self.assertEqual(normalized["_compound_depth"], 3)
        self.assertEqual(normalized["_source_version"], "v0.19.19")
        self.assertIn("wrong_resistance_value", normalized["_compound_mutation_bugs"])
        self.assertEqual(normalized["_parameter_mutations"]["R_charge"]["wrong"], 2.0)

    def test_normalise_compound_four_layer_preserves_topology_bug(self) -> None:
        row = {
            "candidate_id": "v01920_quad_demo",
            "source_model_path": "/tmp/source.mo",
            "mutated_model_path": "/tmp/mutated.mo",
            "workflow_goal": "goal",
            "failure_type": "behavioral_contract_fail",
            "mutation_family": "quad_structural_plus_two_semantic_plus_topology",
            "compound_mutation_bugs": [
                "missing_ground_connects",
                "wrong_capacitor_value",
                "wrong_resistance_value",
                "parallel_leak_resistor",
            ],
            "parameter_mutations": {"R_leak": {"injected_value": 100.0}},
        }

        normalized = _normalise_compound(row, depth=4)

        self.assertEqual(normalized["benchmark_family"], FAMILY_COMPOUND4)
        self.assertEqual(normalized["_compound_depth"], 4)
        self.assertEqual(normalized["_source_version"], "v0.19.20")
        self.assertIn("parallel_leak_resistor", normalized["_compound_mutation_bugs"])
        self.assertEqual(normalized["_parameter_mutations"]["R_leak"]["injected_value"], 100.0)


if __name__ == "__main__":
    unittest.main()
