from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_prompt_ab_v0_19_63 import (
    BASELINE_FAMILY,
    STRUCTURED_TEMPLATE_FAMILY,
    build_bucket_shift,
    build_prompt_ab_summary,
    build_prompt_for_family,
    parse_prompt_families,
    run_prompt_ab,
)


class PromptABV01963Tests(unittest.TestCase):
    def test_build_prompt_for_family_keeps_taxonomy_out(self) -> None:
        task = {
            "task_id": "nl_v1_t1_demo",
            "difficulty": "T1",
            "domain": "thermal",
            "prompt": "Create a small thermal model.",
            "acceptance": ["simulate_pass"],
        }

        prompt = build_prompt_for_family(task, STRUCTURED_TEMPLATE_FAMILY)

        self.assertIn("Return ONLY one JSON object", prompt)
        self.assertIn("Natural-language task", prompt)
        self.assertNotIn("ET01", prompt)
        self.assertNotIn("mutation family", prompt.lower())

    def test_parse_prompt_families_inserts_baseline(self) -> None:
        families = parse_prompt_families(STRUCTURED_TEMPLATE_FAMILY)

        self.assertEqual(families, [BASELINE_FAMILY, STRUCTURED_TEMPLATE_FAMILY])

    def test_build_bucket_shift_uses_common_keys(self) -> None:
        shift = build_bucket_shift({"ET01": 0.5, "ET07": 0.5}, {"ET02": 1.0})

        self.assertEqual(shift["ET01"], -0.5)
        self.assertEqual(shift["ET02"], 1.0)
        self.assertEqual(shift["ET07"], -0.5)

    def test_build_prompt_ab_summary_detects_material_shift(self) -> None:
        family_summaries = {
            BASELINE_FAMILY: {
                "pass_rate": 0.2,
                "d_pq_total_variation": 0.8,
                "generation_failure_distribution_p": {"ET01": 1.0},
            },
            STRUCTURED_TEMPLATE_FAMILY: {
                "pass_rate": 0.4,
                "d_pq_total_variation": 0.7,
                "generation_failure_distribution_p": {"ET07": 1.0},
            },
        }

        summary = build_prompt_ab_summary(
            family_summaries=family_summaries,
            planner_backend="rule",
            dry_run_fixture=True,
        )

        self.assertTrue(summary["success_criterion_met"])
        self.assertEqual(summary["material_shift_families"], [STRUCTURED_TEMPLATE_FAMILY])
        self.assertEqual(
            summary["comparisons"][STRUCTURED_TEMPLATE_FAMILY]["delta_d_pq_vs_baseline"],
            -0.1,
        )

    def test_run_prompt_ab_dry_run_writes_outputs(self) -> None:
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
                                "task_id": "nl_v1_t1_electrical_rc_step",
                                "difficulty": "T1",
                                "domain": "electrical",
                                "prompt": "Create an RC model.",
                                "acceptance": ["simulate_pass"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            summary = run_prompt_ab(
                planner_backend="rule",
                out_dir=out_dir,
                pool_dir=pool_dir,
                dry_run_fixture=True,
            )

            self.assertEqual(summary["status"], "DRY_RUN")
            self.assertEqual(summary["prompt_families"], [BASELINE_FAMILY, STRUCTURED_TEMPLATE_FAMILY])
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())
            self.assertTrue((out_dir / "families" / BASELINE_FAMILY / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()

