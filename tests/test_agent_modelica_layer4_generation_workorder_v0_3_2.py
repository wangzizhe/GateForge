from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_layer4_generation_workorder_v0_3_2 import (
    build_generation_workorder,
    run_generation_workorder,
)


class AgentModelicaLayer4GenerationWorkorderV032Tests(unittest.TestCase):
    def test_build_generation_workorder_maps_family_to_generators(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_l4_workorder_") as td:
            root = Path(td)
            priority = root / "priority.json"
            priority.write_text(
                json.dumps(
                    {
                        "freeze_ready_gap": 14,
                        "family_priorities": [
                            {
                                "family_id": "hard_multiround_simulate_failure",
                                "family_label": "Hard Multi-Round Simulate Failure",
                                "priority_bucket": "priority_1_generate_now",
                                "recommended_new_task_target": 5,
                            },
                            {
                                "family_id": "runtime_numerical_instability",
                                "family_label": "Runtime Numerical Instability",
                                "priority_bucket": "priority_1_generate_now",
                                "recommended_new_task_target": 5,
                            },
                            {
                                "family_id": "initialization_singularity",
                                "family_label": "Initialization Singularity",
                                "priority_bucket": "priority_2_generate_after_p1",
                                "recommended_new_task_target": 4,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            expansion = root / "expansion.json"
            expansion.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "mr_1",
                                "v0_3_family_id": "hard_multiround_simulate_failure",
                                "source_meta": {"library_id": "transform", "model_id": "simplebattery_test"},
                                "failure_type": "cascading_structural_failure",
                            },
                            {
                                "task_id": "rt_1",
                                "v0_3_family_id": "runtime_numerical_instability",
                                "source_meta": {"library_id": "buildings", "model_id": "loads"},
                                "failure_type": "solver_sensitive_simulate_failure",
                            },
                            {
                                "task_id": "init_1",
                                "v0_3_family_id": "initialization_singularity",
                                "origin_task_id": "medium_dual_source_v0",
                                "failure_type": "initialization_infeasible",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_generation_workorder(
                generation_priority_summary_path=str(priority),
                expansion_taskset_path=str(expansion),
            )

        rows = {row["family_id"]: row for row in payload["work_orders"]}
        self.assertEqual(rows["hard_multiround_simulate_failure"]["generator_module"], "gateforge.agent_modelica_multi_round_failure_taskset_v1")
        self.assertEqual(rows["runtime_numerical_instability"]["generator_module"], "gateforge.agent_modelica_wave2_1_harder_dynamics_taskset_v1")
        self.assertEqual(rows["initialization_singularity"]["driver_script"], "scripts/run_agent_modelica_electrical_realism_frozen_taskset_v1.sh")
        self.assertEqual(rows["initialization_singularity"]["focus_models_currently_observed"][0]["library_id"], "electrical_realism")
        self.assertEqual(payload["status"], "READY_FOR_EXECUTION")

    def test_run_generation_workorder_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_l4_workorder_run_") as td:
            root = Path(td)
            priority = root / "priority.json"
            priority.write_text(json.dumps({"freeze_ready_gap": 1, "family_priorities": []}), encoding="utf-8")
            expansion = root / "expansion.json"
            expansion.write_text(json.dumps({"tasks": []}), encoding="utf-8")
            out_dir = root / "out"
            payload = run_generation_workorder(
                generation_priority_summary_path=str(priority),
                expansion_taskset_path=str(expansion),
                out_dir=str(out_dir),
            )
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "summary.md").exists())
            self.assertEqual(payload["status"], "READY_FOR_REVIEW")


if __name__ == "__main__":
    unittest.main()
