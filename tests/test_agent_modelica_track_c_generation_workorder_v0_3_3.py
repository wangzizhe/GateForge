from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_generation_workorder_v0_3_3 import (
    build_generation_workorder,
    run_generation_workorder,
)


class AgentModelicaTrackCGenerationWorkorderV033Tests(unittest.TestCase):
    def test_build_generation_workorder_allocates_targets_from_gap(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_workorder_") as td:
            root = Path(td)
            primary = root / "primary.json"
            v032 = root / "v032.json"
            primary.write_text(
                json.dumps(
                    {
                        "metrics": {"freeze_ready_gap": 10},
                        "excluded_rows": [
                            {
                                "task_id": "a",
                                "v0_3_family_id": "hard_multiround_simulate_failure",
                                "gates": {"holdout_clean": False, "attribution": False, "planner_sensitivity": False},
                            },
                            {
                                "task_id": "b",
                                "v0_3_family_id": "runtime_numerical_instability",
                                "gates": {"holdout_clean": False, "attribution": True, "planner_sensitivity": False},
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            v032.write_text(
                json.dumps(
                    {
                        "work_orders": [
                            {
                                "family_id": "hard_multiround_simulate_failure",
                                "family_label": "Hard MR",
                                "priority_bucket": "priority_1_generate_now",
                                "driver_script": "scripts/a.sh",
                                "manifest_path": "manifest_a.json",
                                "command_hint": "bash scripts/a.sh",
                            },
                            {
                                "family_id": "runtime_numerical_instability",
                                "family_label": "Runtime Num",
                                "priority_bucket": "priority_2_generate_after_p1",
                                "driver_script": "scripts/b.sh",
                                "manifest_path": "manifest_b.json",
                                "command_hint": "bash scripts/b.sh",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_generation_workorder(
                primary_slice_summary_path=str(primary),
                v032_workorder_summary_path=str(v032),
            )
            rows = {row["family_id"]: row for row in payload["work_orders"]}
            self.assertEqual(payload["freeze_ready_gap"], 10)
            self.assertGreater(rows["hard_multiround_simulate_failure"]["recommended_new_task_target_v0_3_3"], 0)
            self.assertGreater(rows["runtime_numerical_instability"]["recommended_new_task_target_v0_3_3"], 0)

    def test_run_generation_workorder_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_workorder_run_") as td:
            root = Path(td)
            primary = root / "primary.json"
            v032 = root / "v032.json"
            primary.write_text(json.dumps({"metrics": {"freeze_ready_gap": 2}, "excluded_rows": []}), encoding="utf-8")
            v032.write_text(
                json.dumps(
                    {
                        "work_orders": [
                            {
                                "family_id": "hard_multiround_simulate_failure",
                                "family_label": "Hard MR",
                                "priority_bucket": "priority_1_generate_now",
                                "driver_script": "scripts/a.sh",
                                "manifest_path": "manifest_a.json",
                                "command_hint": "bash scripts/a.sh",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = run_generation_workorder(
                primary_slice_summary_path=str(primary),
                v032_workorder_summary_path=str(v032),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "READY_FOR_EXECUTION")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "summary.md").exists())


if __name__ == "__main__":
    unittest.main()
