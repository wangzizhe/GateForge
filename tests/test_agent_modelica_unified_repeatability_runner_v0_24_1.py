from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_unified_repeatability_runner_v0_24_1 import (
    build_repeat_plan,
    run_unified_repeatability,
    select_seed_rows,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class UnifiedRepeatabilityRunnerV0241Tests(unittest.TestCase):
    def test_select_seed_rows_filters_family_policy_and_limit(self) -> None:
        seeds = [
            {"seed_id": "b", "mutation_family": "f1", "registry_policy": "p"},
            {"seed_id": "a", "mutation_family": "f1", "registry_policy": "p"},
            {"seed_id": "c", "mutation_family": "f2", "registry_policy": "p"},
        ]

        selected = select_seed_rows(seeds, family="f1", policy="p", limit=1)

        self.assertEqual([row["seed_id"] for row in selected], ["a"])

    def test_build_repeat_plan_disables_routing(self) -> None:
        plan = build_repeat_plan(
            [{"seed_id": "case1", "mutation_family": "f", "source_model": "m"}],
            repeat_count=2,
            max_rounds=8,
            timeout_sec=420,
        )

        self.assertEqual(len(plan), 2)
        self.assertFalse(plan[0]["routing_allowed"])

    def test_run_unified_repeatability_writes_dry_run_outputs(self) -> None:
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
                    }
                ],
            )
            _write_jsonl(
                trajectory_path,
                [
                    {
                        "candidate_id": "case1",
                        "case_id": "case1",
                        "run_id": "reference",
                        "trajectory_class": "multi_turn_useful",
                        "repair_round_count": 2,
                        "final_verdict": "PASS",
                    }
                ],
            )

            summary = run_unified_repeatability(
                seed_registry_path=seed_path,
                reference_trajectory_path=trajectory_path,
                out_dir=out_dir,
                repeat_count=1,
                dry_run=True,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["dry_run"])
            self.assertEqual(summary["selected_seed_count"], 1)
            self.assertTrue((out_dir / "manifest.json").exists())
            self.assertTrue((out_dir / "repeat_plan.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
