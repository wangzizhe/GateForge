from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_slice_note_v0_3_2 import build_slice_note, run_slice_note


class AgentModelicaTrackCSliceNoteV032Tests(unittest.TestCase):
    def test_build_slice_note_promotes_small_planner_lane_to_seed_candidate(self) -> None:
        payload = {
            "lanes": [
                {
                    "lane_id": "planner_sensitive",
                    "label": "Planner-Sensitive Lane",
                    "status": "PASS",
                    "task_count": 6,
                    "success_count": 6,
                    "success_resolution_path_pct": {"llm_planner_assisted": 100.0},
                    "planner_invoked_rate_pct": 100.0,
                    "notes": [],
                },
                {
                    "lane_id": "track_a",
                    "label": "Track A",
                    "status": "PASS",
                    "task_count": 32,
                    "success_count": 32,
                    "success_resolution_path_pct": {"deterministic_rule_only": 100.0},
                    "planner_invoked_rate_pct": 0.0,
                    "notes": [],
                },
            ]
        }
        note = build_slice_note(payload)
        self.assertEqual(note["decision"], "seed_candidate_available_but_no_primary_slice_ready")
        self.assertEqual(note["seed_candidates"][0]["lane_id"], "planner_sensitive")
        self.assertEqual(note["excluded_now"][0]["lane_id"], "track_a")

    def test_run_slice_note_writes_summary_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_track_c_note_") as td:
            root = Path(td)
            audit = root / "audit.json"
            audit.write_text(
                json.dumps(
                    {
                        "lanes": [
                            {
                                "lane_id": "lane",
                                "label": "Lane",
                                "status": "PASS",
                                "task_count": 12,
                                "success_count": 10,
                                "success_resolution_path_pct": {"rule_then_llm": 80.0},
                                "planner_invoked_rate_pct": 90.0,
                                "notes": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = run_slice_note(audit_summary_path=str(audit), out_dir=str(root / "out"))
            self.assertEqual(payload["decision"], "primary_slice_candidate_available")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "summary.md").exists())


if __name__ == "__main__":
    unittest.main()
