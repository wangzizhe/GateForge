from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_multi_round_validation_workorder_v0_3_4 import (
    build_multi_round_validation_workorder,
)


class AgentModelicaMultiRoundValidationWorkorderV034Tests(unittest.TestCase):
    def test_build_multi_round_validation_workorder_selects_freeze_ready_tasks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v034_multiround_workorder_") as td:
            root = Path(td)
            priorities = root / "priorities.json"
            refreshed = root / "refreshed.json"
            priorities.write_text(
                json.dumps(
                    {
                        "best_harder_lane": {
                            "family_id": "hard_multiround_simulate_failure",
                            "freeze_ready_ids": ["task_a", "task_b"],
                        }
                    }
                ),
                encoding="utf-8",
            )
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "task_a",
                                "v0_3_family_id": "hard_multiround_simulate_failure",
                                "failure_type": "coupled_conflict_failure",
                                "source_qualified_model_name": "IBPSA.Examples.A",
                            },
                            {
                                "task_id": "task_b",
                                "v0_3_family_id": "hard_multiround_simulate_failure",
                                "failure_type": "cascading_structural_failure",
                                "source_qualified_model_name": "IBPSA.Examples.B",
                            },
                            {
                                "task_id": "task_c",
                                "v0_3_family_id": "runtime_numerical_instability",
                                "failure_type": "solver_sensitive_simulate_failure",
                                "source_qualified_model_name": "IBPSA.Examples.C",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_multi_round_validation_workorder(
                dev_priorities_summary_path=str(priorities),
                refreshed_candidate_taskset_path=str(refreshed),
                max_tasks=1,
            )
        self.assertEqual(payload.get("status"), "READY_FOR_LOCAL_VALIDATION")
        self.assertEqual(payload.get("selected_family_id"), "hard_multiround_simulate_failure")
        self.assertEqual(payload.get("selected_task_count"), 1)
        tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
        self.assertEqual(tasks[0].get("task_id"), "task_a")
        self.assertEqual(
            ((tasks[0].get("recommended_env") or {}).get("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR")),
            "1",
        )


if __name__ == "__main__":
    unittest.main()
