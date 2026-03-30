from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_layer4_generation_priority_v0_3_2 import (
    build_generation_priority,
    run_generation_priority,
)


class AgentModelicaLayer4GenerationPriorityV032Tests(unittest.TestCase):
    def test_build_generation_priority_ranks_hard_multiround_and_runtime_above_init(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_l4_gen_priority_") as td:
            root = Path(td)
            family_spec = root / "family_spec.json"
            family_spec.write_text(
                json.dumps(
                    {
                        "families": [
                            {
                                "family_id": "initialization_singularity",
                                "display_name": "Initialization Singularity",
                                "enabled_for_v0_3_0": True,
                                "notes": ["prefer controlled initialization conflicts"],
                            },
                            {
                                "family_id": "runtime_numerical_instability",
                                "display_name": "Runtime Numerical Instability",
                                "enabled_for_v0_3_0": True,
                                "notes": ["prefer solver sensitivity"],
                            },
                            {
                                "family_id": "hard_multiround_simulate_failure",
                                "display_name": "Hard Multi-Round Simulate Failure",
                                "enabled_for_v0_3_0": True,
                                "notes": ["prefer budgeted search"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            hard_lane = root / "hard_lane.json"
            hard_lane.write_text(
                json.dumps(
                    {
                        "family_summaries": [
                            {"family_id": "initialization_singularity", "task_count": 6, "gateforge_success_rate_pct": 0.0},
                            {"family_id": "runtime_numerical_instability", "task_count": 6, "gateforge_success_rate_pct": 100.0},
                            {"family_id": "hard_multiround_simulate_failure", "task_count": 18, "gateforge_success_rate_pct": 88.89},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            expansion_summary = root / "expansion_summary.json"
            expansion_summary.write_text(
                json.dumps(
                    {
                        "target_freeze_ready_count": 20,
                        "freeze_ready_count": 6,
                        "excluded_rows": [
                            {"failure_type": "cascading_structural_failure"},
                            {"failure_type": "cascading_structural_failure"},
                            {"failure_type": "coupled_conflict_failure"},
                            {"failure_type": "solver_sensitive_simulate_failure"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            expansion_taskset = root / "taskset.json"
            expansion_taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "seed_a",
                                "classification": "freeze_ready_observed",
                                "multi_step_family": "behavior_then_robustness",
                                "selection_reasons": [
                                    "observed_resolution_path:llm_planner_assisted",
                                    "planner_invoked_observed",
                                    "planner_decisive_observed",
                                    "expected_multi_round",
                                ],
                            },
                            {
                                "task_id": "mr_1",
                                "classification": "proxy_candidate",
                                "v0_3_family_id": "hard_multiround_simulate_failure",
                                "selection_reasons": [
                                    "expected_layer_hint_layer_4",
                                    "expected_multi_round",
                                    "simulate_phase_required",
                                    "mock_success_round_ge_2",
                                    "cascade_depth_ge_2",
                                    "source_result_not_yet_solved",
                                ],
                            },
                            {
                                "task_id": "mr_2",
                                "classification": "proxy_candidate",
                                "v0_3_family_id": "hard_multiround_simulate_failure",
                                "selection_reasons": [
                                    "expected_layer_hint_layer_4",
                                    "expected_multi_round",
                                    "simulate_phase_required",
                                    "mock_success_round_ge_2",
                                    "cascade_depth_ge_2",
                                    "source_result_not_yet_solved",
                                ],
                            },
                            {
                                "task_id": "rt_1",
                                "classification": "proxy_candidate",
                                "v0_3_family_id": "runtime_numerical_instability",
                                "selection_reasons": [
                                    "expected_layer_hint_layer_4",
                                    "mock_success_round_ge_2",
                                    "source_result_multi_round",
                                ],
                            },
                            {
                                "task_id": "init_1",
                                "classification": "proxy_candidate",
                                "v0_3_family_id": "initialization_singularity",
                                "selection_reasons": [
                                    "expected_layer_hint_layer_4",
                                    "source_result_not_yet_solved",
                                ],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = build_generation_priority(
                family_spec_path=str(family_spec),
                hard_lane_summary_path=str(hard_lane),
                expansion_summary_path=str(expansion_summary),
                expansion_taskset_path=str(expansion_taskset),
            )

        self.assertEqual(payload["freeze_ready_gap"], 14)
        family_rows = {row["family_id"]: row for row in payload["family_priorities"]}
        self.assertEqual(family_rows["hard_multiround_simulate_failure"]["priority_bucket"], "priority_1_generate_now")
        self.assertNotEqual(family_rows["initialization_singularity"]["priority_bucket"], "priority_1_generate_now")
        self.assertGreater(
            family_rows["hard_multiround_simulate_failure"]["priority_score"],
            family_rows["runtime_numerical_instability"]["priority_score"],
        )
        self.assertGreater(
            family_rows["runtime_numerical_instability"]["priority_score"],
            family_rows["initialization_singularity"]["priority_score"],
        )
        self.assertEqual(payload["observed_reference_families"][0]["family_id"], "behavior_then_robustness")

    def test_run_generation_priority_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_l4_gen_priority_run_") as td:
            root = Path(td)
            family_spec = root / "family_spec.json"
            family_spec.write_text(
                json.dumps(
                    {
                        "families": [
                            {
                                "family_id": "hard_multiround_simulate_failure",
                                "display_name": "Hard Multi-Round Simulate Failure",
                                "enabled_for_v0_3_0": True,
                                "notes": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            hard_lane = root / "hard_lane.json"
            hard_lane.write_text(json.dumps({"family_summaries": [{"family_id": "hard_multiround_simulate_failure"}]}), encoding="utf-8")
            expansion_summary = root / "expansion_summary.json"
            expansion_summary.write_text(json.dumps({"target_freeze_ready_count": 2, "freeze_ready_count": 0, "excluded_rows": []}), encoding="utf-8")
            expansion_taskset = root / "taskset.json"
            expansion_taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "mr_1",
                                "classification": "proxy_candidate",
                                "v0_3_family_id": "hard_multiround_simulate_failure",
                                "selection_reasons": [
                                    "expected_multi_round",
                                    "simulate_phase_required",
                                    "source_result_not_yet_solved",
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "out"
            payload = run_generation_priority(
                family_spec_path=str(family_spec),
                hard_lane_summary_path=str(hard_lane),
                expansion_summary_path=str(expansion_summary),
                expansion_taskset_path=str(expansion_taskset),
                out_dir=str(out_dir),
            )
            self.assertEqual(payload["status"], "NEEDS_GENERATION_EXECUTION")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "summary.md").exists())


if __name__ == "__main__":
    unittest.main()
