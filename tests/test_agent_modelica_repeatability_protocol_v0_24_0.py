from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_repeatability_protocol_v0_24_0 import (
    build_repeatability_protocol,
    classify_candidate_repeatability,
    classify_family_repeatability,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class RepeatabilityProtocolV0240Tests(unittest.TestCase):
    def test_classify_candidate_repeatability_is_conservative(self) -> None:
        self.assertEqual(
            classify_candidate_repeatability(
                [{"trajectory_class": "multi_turn_useful"}, {"trajectory_class": "multi_turn_useful"}]
            ),
            "stable_true_multi",
        )
        self.assertEqual(
            classify_candidate_repeatability(
                [{"trajectory_class": "multi_turn_useful"}, {"trajectory_class": "multi_turn_failed_or_dead_end"}]
            ),
            "unstable_true_multi",
        )
        self.assertEqual(
            classify_candidate_repeatability(
                [
                    {"trajectory_class": "multi_turn_failed_or_dead_end"},
                    {"trajectory_class": "multi_turn_failed_or_dead_end"},
                ]
            ),
            "stable_dead_end",
        )

    def test_classify_family_repeatability_promotes_with_hard_negatives(self) -> None:
        self.assertEqual(
            classify_family_repeatability(
                [
                    {"repeatability_class": "stable_true_multi"},
                    {"repeatability_class": "stable_true_multi"},
                    {"repeatability_class": "stable_dead_end"},
                ]
            ),
            "family_promotable_with_hard_negatives",
        )

    def test_build_repeatability_protocol_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_path = root / "seed.jsonl"
            trajectory_path = root / "trajectories.jsonl"
            out_dir = root / "out"
            _write_jsonl(
                seed_path,
                [
                    {
                        "seed_id": "case1",
                        "candidate_id": "case1",
                        "mutation_family": "family_a",
                        "source_model": "ModelA",
                        "source_complexity_class": "small",
                        "registry_policy": "benchmark_positive_candidate",
                    },
                    {
                        "seed_id": "case2",
                        "candidate_id": "case2",
                        "mutation_family": "family_a",
                        "source_model": "ModelB",
                        "source_complexity_class": "small",
                        "registry_policy": "hard_negative_candidate",
                    },
                ],
            )
            _write_jsonl(
                trajectory_path,
                [
                    {
                        "candidate_id": "case1",
                        "run_id": "r1",
                        "trajectory_class": "multi_turn_useful",
                        "repair_round_count": 2,
                    },
                    {
                        "candidate_id": "case1",
                        "run_id": "r2",
                        "trajectory_class": "multi_turn_useful",
                        "repair_round_count": 2,
                    },
                    {
                        "candidate_id": "case2",
                        "run_id": "r1",
                        "trajectory_class": "multi_turn_failed_or_dead_end",
                        "repair_round_count": 7,
                    },
                    {
                        "candidate_id": "case2",
                        "run_id": "r2",
                        "trajectory_class": "multi_turn_failed_or_dead_end",
                        "repair_round_count": 7,
                    },
                ],
            )

            summary = build_repeatability_protocol(
                seed_registry_path=seed_path,
                trajectory_path=trajectory_path,
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["candidate_repeatability_counts"]["stable_true_multi"], 1)
            self.assertEqual(summary["candidate_repeatability_counts"]["stable_dead_end"], 1)
            self.assertTrue((out_dir / "protocol.json").exists())
            self.assertTrue((out_dir / "candidate_repeatability.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
