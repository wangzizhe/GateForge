from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_candidate_harvest_v0_3_3 import harvest_candidates


class AgentModelicaTrackCCandidateHarvestV033Tests(unittest.TestCase):
    def test_harvest_candidates_marks_frozen_overlap(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_harvest_") as td:
            root = Path(td)
            taskset = root / "taskset.json"
            frozen = root / "frozen.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "keep_a", "v0_3_family_id": "runtime_numerical_instability"},
                            {"task_id": "drop_a", "v0_3_family_id": "hard_multiround_simulate_failure"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            frozen.write_text(json.dumps({"tasks": [{"task_id": "drop_a"}]}), encoding="utf-8")
            payload = harvest_candidates(
                taskset_paths=[str(taskset)],
                out_dir=str(root / "out"),
                frozen_references=[{"ref_id": "frozen", "path": str(frozen)}],
            )
            rows = {row["task_id"]: row for row in payload["tasks"]}
            self.assertEqual(payload["metrics"]["holdout_clean_count"], 1)
            self.assertTrue(rows["keep_a"]["holdout_clean"])
            self.assertFalse(rows["drop_a"]["holdout_clean"])


if __name__ == "__main__":
    unittest.main()
