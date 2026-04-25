from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_trajectory_schema_v0_23_2 import (
    build_trajectory_schema_index,
    classify_trajectory,
    normalize_observation,
    validate_normalized_trajectory,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class TrajectorySchemaV0232Tests(unittest.TestCase):
    def test_classify_trajectory_uses_repair_rounds_not_attempts(self) -> None:
        self.assertEqual(
            classify_trajectory(repair_round_count=2, final_verdict="PASS"),
            "multi_turn_useful",
        )
        self.assertEqual(
            classify_trajectory(repair_round_count=1, final_verdict="PASS"),
            "single_repair_then_validate",
        )
        self.assertEqual(
            classify_trajectory(repair_round_count=7, final_verdict="FAILED"),
            "multi_turn_failed_or_dead_end",
        )

    def test_normalize_observation_rejects_fake_multiturn(self) -> None:
        normalized = normalize_observation(
            {
                "candidate_id": "case1",
                "run_id": "run1",
                "n_turns": 2,
                "repair_round_count": 1,
                "validation_round_count": 1,
                "executor_status": "PASS",
                "observed_error_sequence": ["model_check_error", "none"],
            },
            source_artifact="artifact.jsonl",
        )

        self.assertFalse(normalized["true_multi_turn"])
        self.assertEqual(normalized["trajectory_class"], "single_repair_then_validate")
        self.assertEqual(validate_normalized_trajectory(normalized), [])

    def test_build_trajectory_schema_index_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            _write_jsonl(
                first,
                [
                    {
                        "candidate_id": "case1",
                        "run_id": "run1",
                        "n_turns": 3,
                        "repair_round_count": 2,
                        "validation_round_count": 1,
                        "executor_status": "PASS",
                        "observed_error_sequence": ["model_check_error", "model_check_error", "none"],
                    }
                ],
            )
            _write_jsonl(
                second,
                [
                    {
                        "candidate_id": "case2",
                        "run_id": "run1",
                        "n_turns": 8,
                        "repair_round_count": 7,
                        "validation_round_count": 1,
                        "executor_status": "FAILED",
                        "observed_error_sequence": ["model_check_error"],
                    }
                ],
            )
            out_dir = root / "out"

            summary = build_trajectory_schema_index(
                input_paths={"first": first, "second": second},
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["trajectory_count"], 2)
            self.assertEqual(summary["trajectory_class_counts"]["multi_turn_useful"], 1)
            self.assertTrue((out_dir / "schema.json").exists())
            self.assertTrue((out_dir / "normalized_trajectories.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
