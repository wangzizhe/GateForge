from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_planner_sensitive_expansion_v0_3_2 import (
    build_expansion_candidates,
    run_expansion,
)


class AgentModelicaPlannerSensitiveExpansionV032Tests(unittest.TestCase):
    def test_build_expansion_candidates_keeps_observed_seed_and_excludes_easy_proxy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_planner_expansion_") as td:
            root = Path(td)
            seed_taskset = root / "seed_taskset.json"
            seed_results = root / "seed_results.json"
            proxy_taskset = root / "proxy_taskset.json"
            proxy_results = root / "proxy_results.json"
            exclusion_taskset = root / "exclusion_taskset.json"
            exclusion_results = root / "exclusion_results.json"

            seed_taskset.write_text(
                json.dumps({"tasks": [{"task_id": "seed_a", "failure_type": "behavior_then_robustness", "expected_rounds_min": 2}]}),
                encoding="utf-8",
            )
            seed_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "seed_a",
                                "resolution_path": "llm_planner_assisted",
                                "planner_invoked": True,
                                "planner_decisive": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proxy_taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "proxy_keep",
                                "failure_type": "cascading_structural_failure",
                                "expected_layer_hint": "layer_4",
                                "expected_rounds_min": 2,
                                "mock_success_round": 3,
                                "simulate_phase_required": True,
                                "cascade_depth": 2,
                            },
                            {
                                "task_id": "proxy_drop",
                                "failure_type": "false_friend_patch_trap",
                                "expected_layer_hint": "layer_4",
                                "expected_rounds_min": 2,
                                "mock_success_round": 2,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proxy_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {"task_id": "proxy_keep", "passed": False, "rounds_used": 2},
                            {"task_id": "proxy_drop", "passed": True, "rounds_used": 1},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            exclusion_taskset.write_text(json.dumps({"tasks": [{"task_id": "proxy_drop"}]}), encoding="utf-8")
            exclusion_results.write_text(
                json.dumps({"results": [{"mutation_id": "proxy_drop", "success": True, "resolution_path": "deterministic_rule_only"}]}),
                encoding="utf-8",
            )

            summary = build_expansion_candidates(
                source_groups=[
                    {
                        "group_id": "seed",
                        "group_label": "Seed",
                        "source_taskset_path": str(seed_taskset),
                        "results_paths": [str(seed_results)],
                        "evidence_tier": "observed_planner_sensitive",
                    },
                    {
                        "group_id": "proxy",
                        "group_label": "Proxy",
                        "source_taskset_path": str(proxy_taskset),
                        "results_paths": [str(proxy_results)],
                        "evidence_tier": "layer4_proxy",
                    },
                    {
                        "group_id": "exclude",
                        "group_label": "Exclude",
                        "source_taskset_path": str(exclusion_taskset),
                        "results_paths": [str(exclusion_results)],
                        "evidence_tier": "deterministic_exclusion_reference",
                    },
                ],
                target_candidate_count=10,
                target_freeze_ready_count=2,
            )
            ids = [row["item_id"] for row in summary["selected_rows"]]
            self.assertEqual(ids, ["seed_a", "proxy_keep"])
            self.assertEqual(summary["freeze_ready_count"], 1)
            self.assertEqual(summary["proxy_candidate_count"], 1)
            self.assertTrue(summary["needs_new_mutation_generation_for_freeze_ready_slice"])

    def test_run_expansion_writes_summary_and_taskset(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_planner_expansion_run_") as td:
            root = Path(td)
            seed_taskset = root / "seed_taskset.json"
            seed_results = root / "seed_results.json"
            seed_taskset.write_text(
                json.dumps({"tasks": [{"task_id": "seed_a", "failure_type": "behavior_then_robustness", "expected_rounds_min": 2}]}),
                encoding="utf-8",
            )
            seed_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "seed_a",
                                "resolution_path": "llm_planner_assisted",
                                "planner_invoked": True,
                                "planner_decisive": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = run_expansion(
                out_dir=str(root / "out"),
                source_groups=[
                    {
                        "group_id": "seed",
                        "group_label": "Seed",
                        "source_taskset_path": str(seed_taskset),
                        "results_paths": [str(seed_results)],
                        "evidence_tier": "observed_planner_sensitive",
                    }
                ],
                target_candidate_count=5,
                target_freeze_ready_count=1,
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "summary.md").exists())
            self.assertTrue((root / "out" / "taskset_candidates.json").exists())


if __name__ == "__main__":
    unittest.main()
