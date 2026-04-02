from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_13_curriculum_closeout import (
    build_curriculum_closeout,
)


class AgentModelicaV0313CurriculumCloseoutTests(unittest.TestCase):
    def test_builds_closeout_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = root / "runtime.json"
            init_source = root / "init_source.json"
            init_family = root / "init_family.json"
            init_live = root / "init_live.json"
            runtime.write_text(json.dumps({"runtime_lane_status": "LIVE_EVIDENCE_READY", "promoted_pair_count": 11, "failed_pair_count": 1}), encoding="utf-8")
            init_source.write_text(json.dumps({"initialization_lane_status": "SEED_ONLY_NO_EXPANSION_HEADROOM", "validated_seed_count": 4}), encoding="utf-8")
            init_family.write_text(json.dumps({"lane_status": "CURRICULUM_READY", "admitted_count": 10}), encoding="utf-8")
            init_live.write_text(json.dumps({"initialization_lane_status": "LIVE_EVIDENCE_READY", "promoted_count": 6, "failed_count": 4}), encoding="utf-8")
            payload = build_curriculum_closeout(
                runtime_live_work_order_path=str(runtime),
                initialization_source_work_order_path=str(init_source),
                initialization_curriculum_family_path=str(init_family),
                initialization_live_work_order_path=str(init_live),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["closeout_status"], "CURRICULUM_CLOSEOUT_READY")
            self.assertEqual(payload["runtime_lane"]["promoted_pair_count"], 11)
            self.assertEqual(payload["initialization_curriculum_lane"]["promoted_count"], 6)


if __name__ == "__main__":
    unittest.main()
