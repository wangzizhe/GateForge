from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_initialization_work_order import (
    build_initialization_work_order,
)


class AgentModelicaV0313InitializationWorkOrderTests(unittest.TestCase):
    def test_marks_seed_only_when_no_preview_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.json"
            source.write_text(
                json.dumps(
                    {
                        "source_count": 4,
                        "preview_queue_count": 0,
                        "target_status_counts": {"validated_initialization_seed": 4},
                    }
                ),
                encoding="utf-8",
            )
            payload = build_initialization_work_order(
                source_summary_path=str(source),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["initialization_lane_status"], "SEED_ONLY_NO_EXPANSION_HEADROOM")
            self.assertEqual(payload["validated_seed_count"], 4)


if __name__ == "__main__":
    unittest.main()
