from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_harder_holdout_ablation_v0_3_1 import (
    _summary_from_results,
    run_harder_holdout_ablation,
)


class AgentModelicaHarderHoldoutAblationV031Tests(unittest.TestCase):
    def test_summary_counts_activation_and_resolution_paths(self) -> None:
        payload = {
            "results": [
                {
                    "success": True,
                    "planner_invoked": True,
                    "planner_decisive": False,
                    "replay_used": False,
                    "rounds_used": 2,
                    "elapsed_sec": 10,
                    "resolution_path": "rule_then_llm",
                    "dominant_stage_subtype": "stage_4_initialization_singularity",
                },
                {
                    "success": False,
                    "planner_invoked": False,
                    "planner_decisive": False,
                    "replay_used": False,
                    "rounds_used": 1,
                    "elapsed_sec": 8,
                    "resolution_path": "unresolved",
                    "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                },
            ]
        }
        summary = _summary_from_results(payload)
        self.assertEqual(summary["task_count"], 2)
        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(summary["planner_invoked_count"], 1)
        self.assertEqual(summary["replay_used_count"], 0)
        self.assertEqual(summary["resolution_path_distribution"]["rule_then_llm"], 1)

    def test_run_marks_inconclusive_when_live_results_show_no_activation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_ablation_") as td:
            root = Path(td)
            pack = root / "pack.json"
            pack.write_text(json.dumps({"cases": [{"mutation_id": "t1"}]}), encoding="utf-8")
            experience = root / "experience.json"
            experience.write_text(json.dumps({"records": []}), encoding="utf-8")

            def _fake_run(cmd, capture_output, text, check):
                out_path = Path(cmd[cmd.index("--out") + 1])
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(
                    json.dumps(
                        {
                            "results": [
                                {
                                    "mutation_id": "t1",
                                    "success": False,
                                    "rounds_used": 1,
                                    "elapsed_sec": 12.0,
                                    "planner_invoked": False,
                                    "planner_decisive": False,
                                    "replay_used": False,
                                    "resolution_path": "unresolved",
                                    "dominant_stage_subtype": "stage_0_none",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0, stdout='{"status":"PASS"}', stderr="")

            with mock.patch("gateforge.agent_modelica_harder_holdout_ablation_v0_3_1.subprocess.run", side_effect=_fake_run):
                payload = run_harder_holdout_ablation(
                    pack_path=str(pack),
                    out_dir=str(root / "out"),
                    planner_backend="rule",
                    experience_source=str(experience),
                )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["activation_summary"]["status"], "inconclusive_low_activation")
            self.assertEqual(payload["ablation_conclusion"], "inconclusive_low_activation")


if __name__ == "__main__":
    unittest.main()
