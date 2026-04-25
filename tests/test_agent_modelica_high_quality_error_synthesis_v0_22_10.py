from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_high_quality_error_synthesis_v0_22_10 import (
    build_high_quality_error_synthesis,
    classify_family_policy,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class HighQualityErrorSynthesisV02210Tests(unittest.TestCase):
    def test_classify_family_policy_separates_family_and_seed_promotion(self) -> None:
        family = classify_family_policy("cap", {"stable_true_multi": 2, "never_true_multi": 1})
        seed = classify_family_policy("sensor", {"stable_true_multi": 1, "never_true_multi": 2})
        rejected = classify_family_policy("bad", {"never_true_multi": 3})

        self.assertEqual(family["policy"], "promote_family_prototype")
        self.assertEqual(seed["policy"], "seed_only")
        self.assertEqual(rejected["policy"], "reject_for_now")

    def test_build_high_quality_error_synthesis_writes_phase_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engineering = root / "engineering.json"
            staged = root / "staged.json"
            single_point = root / "single_point.json"
            family = root / "family.json"
            out_dir = root / "out"
            _write_json(engineering, {"aggregate": {"total_cases": 12, "multi_turn_useful_count": 0}})
            _write_json(staged, {"aggregate": {"total_cases": 12, "multi_turn_useful_count": 6}})
            _write_json(
                single_point,
                {"candidate_stability_counts": {"stable_true_multi": 6, "never_true_multi": 2}},
            )
            _write_json(
                family,
                {
                    "family_stability_counts": {
                        "single_point_capacitor_observability_refactor": {
                            "stable_true_multi": 2,
                            "never_true_multi": 1,
                        },
                        "single_point_sensor_output_abstraction_refactor": {
                            "stable_true_multi": 1,
                            "never_true_multi": 2,
                        },
                    }
                },
            )

            summary = build_high_quality_error_synthesis(
                input_paths={
                    "engineering_screening": engineering,
                    "staged_screening": staged,
                    "single_point_repeatability": single_point,
                    "family_repeatability": family,
                },
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["architecture_handoff"]["ready_to_return_to_agent_framework"])
            self.assertIn("single_point_resistor_observability_refactor", summary["promoted_family_prototypes"])
            self.assertIn("single_point_sensor_output_abstraction_refactor", summary["seed_only_families"])
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
