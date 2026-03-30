from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_resolution_audit_v0_3_2 import (
    build_overall_interpretation,
    run_resolution_audit,
    summarize_lane_payload,
)


class AgentModelicaResolutionAuditV032Tests(unittest.TestCase):
    def test_summarize_lane_payload_from_gf_results_counts_success_paths(self) -> None:
        payload = {
            "results": [
                {
                    "success": True,
                    "resolution_path": "deterministic_rule_only",
                    "dominant_stage_subtype": "stage_2_structural_balance_reference",
                    "planner_invoked": False,
                    "planner_used": False,
                    "planner_decisive": False,
                    "replay_used": True,
                },
                {
                    "success": False,
                    "resolution_path": "unresolved",
                    "dominant_stage_subtype": "stage_3_behavioral_contract_semantic",
                    "planner_invoked": True,
                    "planner_used": True,
                    "planner_decisive": False,
                    "replay_used": False,
                },
            ]
        }
        summary = summarize_lane_payload(
            lane_id="lane_a",
            label="Lane A",
            source_path="dummy.json",
            payload=payload,
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["task_count"], 2)
        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(summary["success_resolution_path_counts"]["deterministic_rule_only"], 1)
        self.assertEqual(summary["planner_invoked_rate_pct"], 50.0)
        self.assertEqual(summary["replay_used_rate_pct"], 50.0)

    def test_summarize_lane_payload_flags_missing_attribution(self) -> None:
        payload = {
            "results": [
                {
                    "success": True,
                    "planner_invoked": False,
                }
            ]
        }
        summary = summarize_lane_payload(
            lane_id="lane_b",
            label="Lane B",
            source_path="dummy.json",
            payload=payload,
        )
        self.assertEqual(summary["status"], "NEEDS_ATTRIBUTION_RERUN")
        self.assertFalse(summary["attribution_available"])

    def test_summarize_lane_payload_from_summary_marks_unresolved_success_anomaly(self) -> None:
        payload = {
            "summary": {
                "total_tasks": 6,
                "success_count": 6,
                "success_at_k_pct": 100.0,
                "resolution_path_distribution": {"unresolved": 6},
                "dominant_stage_subtype_distribution": {"stage_0_none": 6},
                "planner_invoked_rate_pct": 100.0,
                "planner_used_rate_pct": 100.0,
                "planner_decisive_rate_pct": 0.0,
            }
        }
        summary = summarize_lane_payload(
            lane_id="planner_sensitive",
            label="Planner",
            source_path="summary.json",
            payload=payload,
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertTrue(any("unresolved resolution paths" in note for note in summary["notes"]))

    def test_build_overall_interpretation_collects_gaps_and_determinism(self) -> None:
        overall = build_overall_interpretation(
            [
                {
                    "lane_id": "track_a",
                    "status": "PASS",
                    "success_resolution_path_pct": {"deterministic_rule_only": 100.0},
                    "planner_invoked_rate_pct": 0.0,
                    "notes": [],
                },
                {
                    "lane_id": "track_b",
                    "status": "NEEDS_ATTRIBUTION_RERUN",
                    "success_resolution_path_pct": {},
                    "planner_invoked_rate_pct": 0.0,
                    "notes": [],
                },
            ]
        )
        self.assertEqual(overall["status"], "NEEDS_RERUN")
        self.assertIn("track_a", overall["deterministic_dominated_lanes"])
        self.assertIn("track_b", overall["attribution_gap_lanes"])

    def test_run_resolution_audit_writes_summary_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_resolution_audit_") as td:
            root = Path(td)
            lane_path = root / "lane.json"
            lane_path.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "success": True,
                                "resolution_path": "rule_then_llm",
                                "dominant_stage_subtype": "stage_4_initialization_singularity",
                                "planner_invoked": True,
                                "planner_used": True,
                                "planner_decisive": False,
                                "replay_used": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = run_resolution_audit(
                out_dir=str(root / "out"),
                lane_overrides=[
                    {
                        "lane_id": "lane",
                        "label": "Lane",
                        "source_path": str(lane_path),
                    }
                ],
            )
            self.assertEqual(payload["overall"]["status"], "PASS")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "summary.md").exists())


if __name__ == "__main__":
    unittest.main()
