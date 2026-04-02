from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_runtime_pair_preview_taskset import (
    build_runtime_pair_preview_taskset,
)


class AgentModelicaV0313RuntimePairPreviewTasksetTests(unittest.TestCase):
    def test_builds_targeted_tasks_for_requires_preview_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_task_id": "seed_case",
                                "model_hint": "ExampleModel",
                                "source_model_path": "seed.mo",
                                "source_library": "TestLib",
                                "clean_model_text": """\
model ExampleModel
  parameter Real R = 100.0;
  parameter Real C = 0.001;
  parameter Real G = 5.0;
equation
end ExampleModel;""",
                                "allowed_hidden_base_operator": "paired_value_collapse",
                                "default_preset": {"replacement_values": ["0.0", "0.0"]},
                                "pair_statuses": [
                                    {"param_names": ["R", "C"], "status": "validated_runtime_seed"},
                                    {"param_names": ["R", "G"], "status": "requires_preview"},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload = build_runtime_pair_preview_taskset(
                source_manifest_path=str(manifest),
                out_dir=str(root / "out"),
            )

            self.assertEqual(payload["task_count"], 1)
            task = payload["tasks"][0]
            self.assertEqual(task["v0_3_13_candidate_pair"], ["R", "G"])
            self.assertEqual(task["hidden_base_param_names"], ["R", "G"])


if __name__ == "__main__":
    unittest.main()
