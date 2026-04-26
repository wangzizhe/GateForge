from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_replay_harness_v0_24_5 import diff_rows, run_replay_harness


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class ReplayHarnessV0245Tests(unittest.TestCase):
    def test_diff_rows_detects_field_mismatch(self) -> None:
        diffs = diff_rows(
            actual=[{"candidate_id": "a", "repeatability_class": "stable_true_multi"}],
            expected=[{"candidate_id": "a", "repeatability_class": "stable_dead_end"}],
            key="candidate_id",
            fields=["repeatability_class"],
        )

        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0]["diff_type"], "field_mismatch")

    def test_run_replay_harness_matches_expected_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_path = root / "seed.jsonl"
            trajectory_path = root / "trajectories.jsonl"
            expected_candidate = root / "candidate.jsonl"
            expected_family = root / "family.jsonl"
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
                    }
                ],
            )
            _write_jsonl(
                trajectory_path,
                [
                    {"candidate_id": "case1", "case_id": "case1", "run_id": "r1", "trajectory_class": "multi_turn_useful", "repair_round_count": 2},
                    {"candidate_id": "case1", "case_id": "case1", "run_id": "r2", "trajectory_class": "multi_turn_useful", "repair_round_count": 2},
                ],
            )
            _write_jsonl(
                expected_candidate,
                [
                    {
                        "candidate_id": "case1",
                        "repeatability_class": "stable_true_multi",
                        "observation_count": 2,
                        "trajectory_class_counts": {"multi_turn_useful": 2},
                    }
                ],
            )
            _write_jsonl(
                expected_family,
                [
                    {
                        "mutation_family": "family_a",
                        "family_repeatability_class": "family_stable_true_multi",
                        "candidate_repeatability_counts": {"stable_true_multi": 1},
                        "candidate_count": 1,
                    }
                ],
            )

            summary = run_replay_harness(
                seed_registry_path=seed_path,
                trajectory_path=trajectory_path,
                expected_candidate_path=expected_candidate,
                expected_family_path=expected_family,
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["candidate_diff_count"], 0)
            self.assertTrue((out_dir / "replayed_candidate_repeatability.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
