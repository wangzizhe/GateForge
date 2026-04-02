from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_track_c_minimum_matrix_runner_v0_3_2 import run_minimum_matrix


class AgentModelicaTrackCMinimumMatrixRunnerV032Tests(unittest.TestCase):
    def test_run_minimum_matrix_reuses_existing_runs_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_track_c_min_runner_") as td:
            root = Path(td)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "t1"}]}), encoding="utf-8")
            gateforge_results = root / "gateforge_results.json"
            gateforge_results.write_text(
                json.dumps({"records": [{"task_id": "t1", "passed": True, "rounds_used": 1, "elapsed_sec": 1.0}]}),
                encoding="utf-8",
            )
            primary_probe = root / "primary_probe.json"
            primary_probe.write_text(json.dumps({"shared_tool_plane_reached": True}), encoding="utf-8")
            secondary_probe = root / "secondary_probe.json"
            secondary_probe.write_text(json.dumps({"shared_tool_plane_reached": True}), encoding="utf-8")
            slice_summary = root / "slice.json"
            slice_summary.write_text(json.dumps({"status": "NEEDS_MORE_GENERATION"}), encoding="utf-8")
            existing_run_dir = root / "out" / "runs" / "claude_run1"
            existing_run_dir.mkdir(parents=True, exist_ok=True)
            (existing_run_dir / "summary.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            (existing_run_dir / "normalized_bundle.json").write_text(
                json.dumps(
                    {
                        "provider_name": "claude",
                        "arm_id": "arm2_frozen_structured_prompt",
                        "model_id": "claude-test",
                        "record_count": 1,
                        "summary": {"success_rate_pct": 100.0, "infra_failure_count": 0},
                        "records": [{"success": True, "infra_failure": False}],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("subprocess.run") as mocked_run:
                mocked_run.return_value = mock.Mock(returncode=0, stdout='{"status":"PASS"}', stderr="")
                payload = run_minimum_matrix(
                    out_dir=str(root / "out"),
                    taskset_path=str(taskset),
                    gateforge_results_paths=[str(gateforge_results)],
                    primary_probe_summary_path=str(primary_probe),
                    secondary_probe_summary_path=str(secondary_probe),
                    slice_summary_path=str(slice_summary),
                    repeat_count=1,
                    providers=["claude"],
                    skip_existing=True,
                )

            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["classification"], "comparative_path_retained_provisional")
            self.assertEqual(len(payload["run_records"]), 1)
            self.assertTrue(payload["run_records"][0]["reused_existing"])
            mocked_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
