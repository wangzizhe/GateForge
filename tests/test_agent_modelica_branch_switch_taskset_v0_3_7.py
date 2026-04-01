from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_branch_switch_taskset_v0_3_7 import (
    build_branch_candidates,
    build_branch_switch_task,
    build_branch_switch_taskset,
)


def _source_task(task_id: str = "v036_rc_dual_collapse", operator: str = "paired_value_collapse") -> dict:
    return {
        "task_id": task_id,
        "hidden_base_operator": operator,
        "mutation_spec": {
            "hidden_base": {
                "audit": {
                    "mutations": [
                        {"param_name": "R", "original_value": "100.0", "new_value": "0.0"},
                        {"param_name": "C", "original_value": "0.001", "new_value": "0.0"},
                    ]
                }
            }
        },
    }


class BranchSwitchTasksetTests(unittest.TestCase):
    def test_build_branch_candidates_from_mutations(self) -> None:
        branches = build_branch_candidates(_source_task())
        self.assertEqual(len(branches), 2)
        self.assertEqual(branches[0]["branch_id"], "continue_on_R")
        self.assertEqual(branches[1]["branch_id"], "switch_to_C")

    def test_build_branch_switch_task_returns_none_for_wrong_operator(self) -> None:
        self.assertIsNone(build_branch_switch_task(_source_task(operator="paired_value_bias_shift")))

    def test_build_branch_switch_task_sets_structured_fields(self) -> None:
        payload = build_branch_switch_task(_source_task())
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["required_entry_bucket"], "stalled_search_after_progress")
        self.assertEqual(payload["current_branch"], "continue_on_R")
        self.assertEqual(payload["preferred_branch"], "switch_to_C")
        self.assertEqual(payload["residual_hidden_parameters"], ["R", "C"])
        self.assertEqual(payload["baseline_measurement_protocol"]["enabled_policy_flags"]["allow_branch_switch_replan_policy"], False)

    def test_build_branch_switch_taskset_filters_non_collapse_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v037_taskset_") as td:
            root = Path(td)
            source = root / "source.json"
            source.write_text(
                json.dumps(
                    {
                        "tasks": [
                            _source_task("good1"),
                            _source_task("good2"),
                            _source_task("skip1", operator="paired_value_bias_shift"),
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_branch_switch_taskset(
                source_taskset_path=str(source),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload["task_count"], 2)
        self.assertEqual(payload["task_ids"], ["good1", "good2"])
        self.assertIn("skip1", payload["skipped_task_ids"])


if __name__ == "__main__":
    unittest.main()
