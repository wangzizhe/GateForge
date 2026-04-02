from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_runtime_pair_inventory import (
    build_runtime_pair_inventory,
)


class AgentModelicaV0313RuntimePairInventoryTests(unittest.TestCase):
    def test_collects_preview_queue_from_source_manifest(self) -> None:
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

            payload = build_runtime_pair_inventory(
                source_manifest_path=str(manifest),
                out_dir=str(root / "out"),
            )

            self.assertEqual(payload["inventory_count"], 2)
            self.assertEqual(payload["preview_queue_count"], 1)
            self.assertEqual(payload["status_counts"]["validated_runtime_seed"], 1)
            self.assertEqual(payload["preview_queue"][0]["param_names"], ["R", "G"])


if __name__ == "__main__":
    unittest.main()
