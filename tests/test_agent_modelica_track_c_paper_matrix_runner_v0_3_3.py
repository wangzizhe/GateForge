from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_track_c_paper_matrix_runner_v0_3_3 import run_paper_matrix


class AgentModelicaTrackCPaperMatrixRunnerV033Tests(unittest.TestCase):
    def test_run_paper_matrix_reuses_existing_provider_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_paper_matrix_runner_") as td:
            root = Path(td)
            taskset = root / "taskset.json"
            taskset.write_text(json.dumps({"tasks": [{"task_id": "t1"}]}), encoding="utf-8")
            gateforge_results = root / "gateforge_results.json"
            gateforge_results.write_text(
                json.dumps({"records": [{"task_id": "t1", "passed": True, "rounds_used": 1, "elapsed_sec": 2.0}]}),
                encoding="utf-8",
            )

            claude_run_dir = root / "out" / "runs" / "claude_run1"
            claude_run_dir.mkdir(parents=True, exist_ok=True)
            (claude_run_dir / "summary.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            (claude_run_dir / "normalized_bundle.json").write_text(
                json.dumps(
                    {
                        "provider_name": "claude",
                        "arm_id": "arm2_frozen_structured_prompt",
                        "model_id": "claude-test",
                        "record_count": 1,
                        "summary": {
                            "success_rate_pct": 100.0,
                            "infra_failure_count": 0,
                            "avg_wall_clock_sec": 20.0,
                            "avg_omc_tool_call_count": 2.0,
                        },
                        "records": [
                            {
                                "task_id": "t1",
                                "success": True,
                                "infra_failure": False,
                                "omc_tool_call_count": 2,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("subprocess.run") as mocked_run:
                mocked_run.return_value = mock.Mock(returncode=0, stdout='{"status":"PASS"}', stderr="")
                payload = run_paper_matrix(
                    taskset_path=str(taskset),
                    gateforge_results_paths=[str(gateforge_results)],
                    out_dir=str(root / "out"),
                    claude_repeat=1,
                    codex_repeat=0,
                    skip_existing=True,
                )

            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["provider_repeats"]["claude"], 1)
            self.assertEqual(len(payload["provider_rows"]), 2)
            self.assertEqual(payload["run_records"][0]["provider_name"], "claude")
            self.assertTrue(payload["run_records"][0]["reused_existing"])
            mocked_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
