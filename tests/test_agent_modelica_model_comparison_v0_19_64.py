from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_model_comparison_v0_19_64 import (
    ModelProfile,
    build_model_comparison_summary,
    parse_model_profiles,
    run_model_comparison,
    select_stratified_tasks,
)


class ModelComparisonV01964Tests(unittest.TestCase):
    def test_parse_model_profiles(self) -> None:
        profiles = parse_model_profiles("gem:gemini:gemini-x,son:anthropic:claude-sonnet")

        self.assertEqual(profiles[0], ModelProfile("gem", "gemini", "gemini-x"))
        self.assertEqual(profiles[1].provider_backend, "anthropic")

    def test_parse_model_profiles_rejects_invalid_spec(self) -> None:
        with self.assertRaises(ValueError):
            parse_model_profiles("bad-spec")

    def test_select_stratified_tasks_covers_difficulties_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pool_dir = Path(tmp)
            tasks = []
            for difficulty in ("T1", "T2", "T3", "T4", "T5", "T1"):
                tasks.append(
                    {
                        "task_id": f"task_{len(tasks)}",
                        "difficulty": difficulty,
                        "domain": "demo",
                        "prompt": "Build a model.",
                        "acceptance": ["simulate_pass"],
                    }
                )
            (pool_dir / "tasks.json").write_text(json.dumps({"tasks": tasks}), encoding="utf-8")

            selected = select_stratified_tasks(pool_dir=pool_dir, max_tasks=5)

            self.assertEqual([task["difficulty"] for task in selected], ["T1", "T2", "T3", "T4", "T5"])

    def test_build_model_comparison_summary_marks_partial_without_sonnet(self) -> None:
        summary = build_model_comparison_summary(
            profile_summaries={
                "gem": {
                    "model": "gemini-2.5-flash-lite",
                    "provider_backend": "gemini",
                    "task_count": 2,
                    "pass_rate": 0.5,
                    "d_pq_total_variation": 0.8,
                    "bucket_counts": {"PASS": 1, "ET01": 1},
                }
            },
            blocked_profiles=[
                {
                    "model_profile_id": "sonnet",
                    "provider_backend": "anthropic",
                    "model": "claude-sonnet",
                    "blocker": "missing_anthropic_api_key",
                }
            ],
            dry_run_fixture=False,
            task_ids=["a", "b"],
        )

        self.assertEqual(summary["status"], "PARTIAL")
        self.assertFalse(summary["success_criterion_met"])

    def test_run_model_comparison_dry_run_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pool_dir = root / "pool"
            out_dir = root / "out"
            pool_dir.mkdir()
            (pool_dir / "tasks.json").write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "nl_v1_t1_thermal_lumped_wall",
                                "difficulty": "T1",
                                "domain": "thermal",
                                "prompt": "Create a thermal wall model.",
                                "acceptance": ["simulate_pass"],
                            },
                            {
                                "task_id": "nl_v1_t2_fluid_tank_outflow",
                                "difficulty": "T2",
                                "domain": "fluid",
                                "prompt": "Create a tank model.",
                                "acceptance": ["simulate_pass"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            summary = run_model_comparison(
                out_dir=out_dir,
                pool_dir=pool_dir,
                model_profiles="gem:gemini:gemini-x,son:anthropic:claude-sonnet",
                max_tasks=2,
                dry_run_fixture=True,
            )

            self.assertEqual(summary["status"], "DRY_RUN")
            self.assertEqual(summary["completed_profiles"], ["gem", "son"])
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "profiles" / "gem" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()

