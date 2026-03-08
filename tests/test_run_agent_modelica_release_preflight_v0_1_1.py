import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunAgentModelicaReleasePreflightV011Tests(unittest.TestCase):
    def test_fallback_mutant_generation_uses_real_newlines(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "run_agent_modelica_release_preflight_v0_1_1.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('lambda _: "equation\\n" + injection', script)
        self.assertIn('insert = "equation\\n" + injection + "\\n"', script)
        self.assertIn('mutated_text = source_text + "\\nequation\\n" + injection + "\\n"', script)
        self.assertNotIn('"equation\\\\n" + injection', script)
        self.assertNotIn('"\\\\nequation\\\\n" + injection', script)

    def test_script_integrates_l3_diagnostic_gate_and_summary_fields(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "run_agent_modelica_release_preflight_v0_1_1.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("ENABLE_L3_DIAGNOSTIC_GATE", script)
        self.assertIn("ENFORCE_L3_DIAGNOSTIC_GATE", script)
        self.assertIn("LIVE_SMOKE_EXECUTOR_MODULE", script)
        self.assertIn("python3 -m gateforge.agent_modelica_diagnostic_quality_v0", script)
        self.assertIn("python3 -m gateforge.agent_modelica_l3_diagnostic_gate_v0", script)
        self.assertIn('"l3_diagnostic_gate_status"', script)
        self.assertIn('"l3_parse_coverage_pct"', script)
        self.assertIn('"l3_type_match_rate_pct"', script)
        self.assertIn('"l3_stage_match_rate_pct"', script)

    def test_script_runs_live_smoke_path_with_mock_executor(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_release_preflight_v0_1_1.sh"

        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "release_preflight"
            env = {
                **os.environ,
                "GATEFORGE_AGENT_MVP_PROFILE_PATH": str(repo_root / "benchmarks" / "agent_modelica_mvp_repair_v1.json"),
                "GATEFORGE_AGENT_RELEASE_OUT_DIR": str(out_dir),
                "GATEFORGE_AGENT_RELEASE_RUN_LIVE_SMOKE": "1",
                "GATEFORGE_AGENT_RELEASE_REQUIRE_REAL_OMC_BACKEND": "0",
                "GATEFORGE_AGENT_RELEASE_SMOKE_EXECUTOR_MODULE": "gateforge.agent_modelica_live_executor_mock_v0",
                "GATEFORGE_AGENT_RELEASE_SMOKE_BACKEND": "mock",
                "GATEFORGE_AGENT_RELEASE_SMOKE_FAILURE_TYPE": "simulate_error",
                "GATEFORGE_AGENT_RELEASE_SMOKE_EXPECTED_STAGE": "simulate",
            }
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            summary = json.loads((out_dir / "release_preflight_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("live_smoke_status"), "PASS")
            self.assertEqual(summary.get("live_smoke_backend_used"), "mock")
            self.assertEqual(summary.get("l3_diagnostic_gate_status"), "PASS")
            self.assertEqual(float(summary.get("l3_parse_coverage_pct") or 0.0), 100.0)


if __name__ == "__main__":
    unittest.main()
