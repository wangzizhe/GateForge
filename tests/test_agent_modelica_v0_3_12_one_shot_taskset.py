from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_12_one_shot_taskset import (
    build_v0_3_12_one_shot_taskset,
)


class AgentModelicaV0312OneShotTasksetTests(unittest.TestCase):
    def test_builds_combined_taskset_from_legacy_and_bias_shift_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy = root / "legacy.json"
            legacy.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "legacy_one",
                                "current_branch": "continue_on_a",
                                "selected_branch": "continue_on_a",
                                "detected_branch_sequence": ["continue_on_a"],
                                "candidate_branches": [{"branch_id": "continue_on_a"}, {"branch_id": "switch_to_b"}],
                            }
                        ]
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
                                "task_id": "bias_one",
                                "hidden_base_operator": "paired_value_bias_shift",
                                "mutation_spec": {
                                    "hidden_base": {
                                        "audit": {
                                            "mutations": [
                                                {"param_name": "K"},
                                                {"param_name": "T"},
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "task_id": "skip_me",
                                "hidden_base_operator": "paired_value_collapse",
                                "mutation_spec": {
                                    "hidden_base": {
                                        "audit": {
                                            "mutations": [
                                                {"param_name": "x"},
                                                {"param_name": "y"},
                                            ]
                                        }
                                    }
                                },
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_12_one_shot_taskset(
                legacy_taskset_path=str(legacy),
                expansion_source_taskset_path=str(expansion),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["task_count"], 2)
            self.assertEqual(payload["task_ids"], ["legacy_one", "bias_one"])
            expansion_task = payload["tasks"][1]
            self.assertEqual(expansion_task["selected_branch"], "continue_on_K")
            self.assertEqual(expansion_task["preferred_branch"], "switch_to_T")


if __name__ == "__main__":
    unittest.main()
