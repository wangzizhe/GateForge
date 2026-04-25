from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_seed_registry_v0_23_1 import (
    build_seed_registry,
    classify_seed_policy,
    normalize_candidate_summary,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class SeedRegistryV0231Tests(unittest.TestCase):
    def test_classify_seed_policy_separates_benchmark_seed_and_hard_negative(self) -> None:
        self.assertEqual(
            classify_seed_policy(
                mutation_family="single_point_resistor_observability_refactor",
                stability="stable_true_multi",
            ),
            "benchmark_positive_candidate",
        )
        self.assertEqual(
            classify_seed_policy(
                mutation_family="single_point_sensor_output_abstraction_refactor",
                stability="stable_true_multi",
            ),
            "seed_only_positive_candidate",
        )
        self.assertEqual(
            classify_seed_policy(
                mutation_family="single_point_source_parameterization_refactor",
                stability="unstable_true_multi",
            ),
            "research_unstable_candidate",
        )
        self.assertEqual(
            classify_seed_policy(
                mutation_family="single_point_capacitor_observability_refactor",
                stability="never_true_multi",
            ),
            "hard_negative_candidate",
        )

    def test_normalize_candidate_summary_disables_routing(self) -> None:
        row = normalize_candidate_summary(
            {
                "candidate_id": "v0226_001_single_point_resistor_observability_SmallRCConstantV0",
                "stability": "stable_true_multi",
                "observation_count": 2,
                "true_multi_observation_count": 2,
                "repair_round_counts": [2, 2],
                "qualities": ["multi_turn_useful", "multi_turn_useful"],
            },
            source_artifact="artifacts/demo/summary.json",
            default_family="single_point_resistor_observability_refactor",
        )

        self.assertFalse(row["routing_allowed"])
        self.assertEqual(row["source_model"], "SmallRCConstantV0")
        self.assertEqual(row["registry_policy"], "benchmark_positive_candidate")

    def test_build_seed_registry_writes_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resistor = root / "resistor.json"
            family = root / "family.json"
            out_dir = root / "out"
            _write_json(
                resistor,
                {
                    "candidate_summaries": [
                        {
                            "candidate_id": "v0226_001_single_point_resistor_observability_SmallRCConstantV0",
                            "stability": "stable_true_multi",
                            "observation_count": 2,
                            "true_multi_observation_count": 2,
                            "repair_round_counts": [2, 2],
                            "qualities": ["multi_turn_useful", "multi_turn_useful"],
                        }
                    ]
                },
            )
            _write_json(
                family,
                {
                    "candidate_summaries": [
                        {
                            "candidate_id": "v0228_001_single_point_capacitor_observability_refactor_MediumRLCSeriesV0",
                            "mutation_family": "single_point_capacitor_observability_refactor",
                            "stability": "never_true_multi",
                            "observation_count": 2,
                            "true_multi_observation_count": 0,
                            "repair_round_counts": [7, 7],
                            "qualities": ["dead_end_hard", "dead_end_hard"],
                        }
                    ]
                },
            )

            summary = build_seed_registry(
                input_paths={"resistor_repeatability": resistor, "family_repeatability": family},
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["seed_count"], 2)
            self.assertEqual(summary["registry_policy_counts"]["benchmark_positive_candidate"], 1)
            self.assertEqual(summary["registry_policy_counts"]["hard_negative_candidate"], 1)
            self.assertTrue((out_dir / "seed_registry.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
