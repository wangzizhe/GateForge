from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_abandon_regenerate_v0_19_62 import (
    build_abandon_regenerate_summary,
    estimate_repair_cost,
    run_abandon_regenerate,
    should_abandon_and_regenerate,
)


def _result(task_id: str, bucket_id: str, status: str = "fail") -> dict:
    return {
        "task_id": task_id,
        "difficulty": "T1",
        "domain": "electrical",
        "final_status": status,
        "model_name": task_id,
        "model_text": f"model {task_id}\n Real x;\nequation\n x = 1;\nend {task_id};",
        "classification": {
            "bucket_id": bucket_id,
            "classification_source": "fixture",
            "evidence_excerpt": "fixture evidence",
        },
    }


class AbandonRegenerateV01962Tests(unittest.TestCase):
    def test_estimate_repair_cost_by_bucket(self) -> None:
        self.assertEqual(estimate_repair_cost(_result("a", "ET01")), 3.0)
        self.assertEqual(estimate_repair_cost(_result("a", "ET07")), 1.0)
        self.assertEqual(estimate_repair_cost(_result("a", "PASS", "pass")), 0.0)

    def test_should_abandon_uses_budget_gate(self) -> None:
        self.assertTrue(should_abandon_and_regenerate(_result("a", "ET01")))
        self.assertFalse(should_abandon_and_regenerate(_result("a", "ET07")))
        self.assertFalse(should_abandon_and_regenerate(_result("a", "PASS", "pass")))

    def test_build_summary_reports_non_degrading_regeneration(self) -> None:
        baseline = [_result("a", "ET01"), _result("b", "PASS", "pass")]
        final = [{**baseline[0], "final_status": "pass"}, baseline[1]]
        regen = [final[0]]

        summary = build_abandon_regenerate_summary(
            baseline_results=baseline,
            final_results=final,
            regeneration_results=regen,
            planner_backend="fixture",
            dry_run_fixture=True,
            generation_cost=1.0,
            repair_cost_multiplier=1.5,
            min_no_improvement_rounds=1,
        )

        self.assertEqual(summary["without_abandon_pass_rate"], 0.5)
        self.assertEqual(summary["with_abandon_pass_rate"], 1.0)
        self.assertTrue(summary["success_criterion_met"])

    def test_run_abandon_regenerate_dry_run_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            tasks_dir = input_dir / "tasks"
            tasks_dir.mkdir(parents=True)
            (tasks_dir / "nl_v1_t1_thermal_lumped_wall.json").write_text(
                json.dumps(_result("nl_v1_t1_thermal_lumped_wall", "ET01")),
                encoding="utf-8",
            )
            (tasks_dir / "nl_v1_t1_mechanical_mass_damper.json").write_text(
                json.dumps(_result("nl_v1_t1_mechanical_mass_damper", "PASS", "pass")),
                encoding="utf-8",
            )
            pool = root / "pool"
            pool.mkdir()
            (pool / "tasks.json").write_text(
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
                                "task_id": "nl_v1_t1_mechanical_mass_damper",
                                "difficulty": "T1",
                                "domain": "mechanical",
                                "prompt": "Create a mass damper model.",
                                "acceptance": ["simulate_pass"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "out"

            summary = run_abandon_regenerate(
                planner_backend="rule",
                input_dir=input_dir,
                out_dir=out_dir,
                pool_dir=pool,
                dry_run_fixture=True,
            )

            self.assertEqual(summary["status"], "DRY_RUN")
            self.assertEqual(summary["abandon_trigger_count"], 1)
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "regeneration_attempts.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

