from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_matrix_v0_3_2 import (
    build_gateforge_bundle_from_results_paths,
    summarize_track_c_matrix,
)


class AgentModelicaTrackCMatrixV032Tests(unittest.TestCase):
    def test_build_gateforge_bundle_from_results_paths_filters_to_taskset(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_track_c_matrix_") as td:
            root = Path(td)
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"task_id": "t1"},
                            {"task_id": "t2"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results_a = root / "results_a.json"
            results_a.write_text(
                json.dumps(
                    {
                        "records": [
                            {"task_id": "t1", "passed": True, "rounds_used": 2, "elapsed_sec": 12.0, "resolution_path": "llm_planner_assisted"},
                            {"task_id": "skip", "passed": False},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            results_b = root / "results_b.json"
            results_b.write_text(
                json.dumps(
                    {
                        "records": [
                            {"task_id": "t2", "passed": False, "rounds_used": 1, "elapsed_sec": 5.0, "current_fail_bucket": "oscillation"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_path = root / "gateforge_bundle.json"
            bundle = build_gateforge_bundle_from_results_paths(
                taskset_path=str(taskset),
                results_paths=[str(results_a), str(results_b)],
                out_path=str(out_path),
            )
            self.assertEqual(bundle["provider_name"], "gateforge")
            self.assertEqual(bundle["record_count"], 2)
            self.assertEqual(bundle["summary"]["success_count"], 1)

    def test_summarize_track_c_matrix_builds_variance_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_track_c_matrix_") as td:
            root = Path(td)
            bundle_a = root / "a.json"
            bundle_b = root / "b.json"
            bundle_a.write_text(
                json.dumps(
                    {
                        "provider_name": "claude",
                        "arm_id": "arm2",
                        "model_id": "claude-test",
                        "record_count": 2,
                        "summary": {"success_rate_pct": 50.0, "infra_failure_count": 0},
                        "records": [
                            {"success": True, "infra_failure": False},
                            {"success": False, "infra_failure": False},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            bundle_b.write_text(
                json.dumps(
                    {
                        "provider_name": "claude",
                        "arm_id": "arm2",
                        "model_id": "claude-test",
                        "record_count": 2,
                        "summary": {"success_rate_pct": 100.0, "infra_failure_count": 0},
                        "records": [
                            {"success": True, "infra_failure": False},
                            {"success": True, "infra_failure": False},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            summary = summarize_track_c_matrix(bundle_paths=[str(bundle_a), str(bundle_b)], out_dir=str(root / "out"))
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(len(summary["variance_summary"]), 1)
            self.assertEqual(summary["variance_summary"][0]["run_count"], 2)
            self.assertEqual(summary["variance_summary"][0]["spread_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
