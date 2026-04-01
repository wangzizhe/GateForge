from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_9_manifests import build_v0_3_9_manifests


class AgentModelicaV039ManifestsTests(unittest.TestCase):
    def test_builds_mainline_and_contrast_manifests_from_live_split(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "a", "success_after_branch_switch": True, "success_without_branch_switch_evidence": False},
                            {"task_id": "b", "success_after_branch_switch": False, "success_without_branch_switch_evidence": True},
                            {"task_id": "c", "success_after_branch_switch": True, "success_without_branch_switch_evidence": False},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            lane = root / "lane.json"
            lane.write_text(json.dumps({"lane_status": "CANDIDATE_READY"}), encoding="utf-8")
            payload = build_v0_3_9_manifests(
                refreshed_summary_path=str(refreshed),
                lane_summary_path=str(lane),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["status"], "PASS")
            mainline = json.loads((root / "out" / "mainline_manifest.json").read_text(encoding="utf-8"))
            contrast = json.loads((root / "out" / "contrast_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(mainline["task_count"], 3)
            self.assertEqual(mainline["explicit_branch_switch_subset_task_ids"], ["a", "c"])
            self.assertEqual(contrast["task_ids"], ["b"])


if __name__ == "__main__":
    unittest.main()
