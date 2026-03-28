from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_cross_domain_matrix_runner_v1 import (
    build_config_commands,
    run_matrix,
)


class AgentModelicaCrossDomainMatrixRunnerV1Tests(unittest.TestCase):
    def test_build_config_commands_emits_four_configs(self) -> None:
        rows = build_config_commands(
            pack_path="pack.json",
            out_dir="artifacts/x",
            planner_backend="gemini",
            comparison_backend="gemini",
            max_rounds=8,
            timeout_sec=300,
            comparison_timeout_sec=120,
            experience_source="/tmp/exp.json",
            planner_experience_max_tokens=320,
        )
        self.assertEqual(len(rows), 4)
        labels = [row["config_label"] for row in rows]
        self.assertEqual(labels, ["baseline", "replay_only", "planner_only", "replay_plus_planner"])
        replay_cmd = rows[1]["runner_cmd"]
        planner_cmd = rows[2]["runner_cmd"]
        self.assertIn("--experience-replay", replay_cmd)
        self.assertIn("--planner-experience-injection", planner_cmd)

    def test_run_matrix_dry_run_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "matrix"
            summary = run_matrix(
                track_id="buildings_v1",
                library="Buildings",
                pack_path="pack.json",
                out_dir=str(out_dir),
                experience_source="/tmp/exp.json",
                dry_run=True,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "matrix_summary.json").exists())
            self.assertEqual(len(summary["configs"]), 4)
            self.assertEqual(summary["configs"][0]["status"], "PLANNED")
            self.assertTrue(str(summary.get("layer_sidecar") or "").endswith("layer_metadata.json"))

    def test_run_matrix_requires_experience_source_for_non_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "matrix"
            with mock.patch(
                "gateforge.agent_modelica_cross_domain_matrix_runner_v1._run",
                return_value=(0, "{}", ""),
            ):
                summary = run_matrix(
                    track_id="buildings_v1",
                    library="Buildings",
                    pack_path="pack.json",
                    out_dir=str(out_dir),
                    experience_source="",
                    dry_run=False,
                )
            self.assertEqual(summary["status"], "FAIL")
            self.assertEqual(summary["configs"][1]["reason"], "experience_source_missing")

    def test_run_matrix_executes_runner_and_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "matrix"
            pack = Path(d) / "pack.json"
            pack.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "mutation_id": "m1",
                                "expected_failure_type": "semantic_regression",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            def fake_run(cmd: list[str]) -> tuple[int, str, str]:
                cmd_s = " ".join(cmd)
                if "agent_modelica_gf_hardpack_runner_v1" in cmd_s:
                    out_idx = cmd.index("--out") + 1
                    Path(cmd[out_idx]).write_text(
                        json.dumps(
                            {
                                "results": [
                                    {
                                        "mutation_id": "m1",
                                        "success": True,
                                        "resolution_attribution": {
                                            "dominant_stage_subtype": "stage_3_behavioral_contract_semantic"
                                        },
                                    }
                                ]
                            }
                        ),
                        encoding="utf-8",
                    )
                elif "agent_modelica_generalization_benchmark_v1" in cmd_s:
                    out_idx = cmd.index("--out") + 1
                    Path(cmd[out_idx]).write_text(
                        json.dumps(
                            {
                                "bare_llm_results": [{"mutation_id": "m1", "success": True}],
                                "bare_llm_metrics": {"repair_rate": 1.0, "total": 1},
                                "gateforge_metrics": {"repair_rate": 1.0, "total": 1},
                            }
                        ),
                        encoding="utf-8",
                    )
                return 0, "{}", ""

            with mock.patch(
                "gateforge.agent_modelica_cross_domain_matrix_runner_v1._run",
                side_effect=fake_run,
            ) as run_mock:
                summary = run_matrix(
                    track_id="buildings_v1",
                    library="Buildings",
                    pack_path=str(pack),
                    out_dir=str(out_dir),
                    experience_source="/tmp/exp.json",
                    dry_run=False,
                )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(run_mock.call_count, 8)
            self.assertEqual(summary["configs"][-1]["status"], "PASS")
            self.assertTrue((out_dir / "baseline").exists())
            self.assertTrue((out_dir / "replay_plus_planner").exists())
            self.assertTrue((out_dir / "layer_metadata.json").exists())
            self.assertEqual(summary["layer_sidecar_summary"]["observed_count"], 1)

    def test_cli_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "matrix"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_cross_domain_matrix_runner_v1",
                    "--track-id",
                    "buildings_v1",
                    "--library",
                    "Buildings",
                    "--pack",
                    "pack.json",
                    "--out-dir",
                    str(out_dir),
                    "--experience-source",
                    "/tmp/exp.json",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads((out_dir / "matrix_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")


if __name__ == "__main__":
    unittest.main()
