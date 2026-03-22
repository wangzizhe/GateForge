import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunAgentModelicaReleasePreflightV011Tests(unittest.TestCase):
    def test_v012_wrapper_sets_release_artifact_dir(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "run_agent_modelica_release_preflight_v0_1_2.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('GATEFORGE_AGENT_RELEASE_OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_2}"', script)
        self.assertIn("exec bash scripts/run_agent_modelica_release_preflight_v0_1_1.sh", script)

    def test_v013_wrapper_sets_release_artifact_dir(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "run_agent_modelica_release_preflight_v0_1_3.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('GATEFORGE_AGENT_RELEASE_OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_3}"', script)
        self.assertIn("bash scripts/run_agent_modelica_release_preflight_v0_1_1.sh", script)
        self.assertIn("python3 -m gateforge.agent_modelica_release_preflight_v0_1_3_evidence", script)

    def test_v014_wrapper_sets_release_artifact_dir(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "run_agent_modelica_release_preflight_v0_1_4.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('GATEFORGE_AGENT_RELEASE_OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_4}"', script)
        self.assertIn("bash scripts/run_agent_modelica_release_preflight_v0_1_3.sh", script)
        self.assertIn("python3 -m gateforge.agent_modelica_release_preflight_v0_1_4_evidence", script)

    def test_v015_wrapper_sets_release_artifact_dir(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "run_agent_modelica_release_preflight_v0_1_5.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('GATEFORGE_AGENT_RELEASE_OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_5}"', script)
        self.assertIn("bash scripts/run_agent_modelica_release_preflight_v0_1_4.sh", script)
        self.assertIn("python3 -m gateforge.agent_modelica_release_preflight_v0_1_5_evidence", script)

    def test_v013_evidence_module_augments_summary(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            summary_path = tmp / "release_preflight_summary.json"
            robustness_baseline = tmp / "robustness_baseline.json"
            robustness_deterministic = tmp / "robustness_deterministic.json"
            multistep_baseline = tmp / "multistep_baseline.json"

            summary_path.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "reasons": [],
                        "live_smoke_status": "PASS",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            robustness_baseline.write_text(
                json.dumps({"all_scenarios_pass_pct": 11.11}, indent=2),
                encoding="utf-8",
            )
            robustness_deterministic.write_text(
                json.dumps({"success_at_k_pct": 100.0}, indent=2),
                encoding="utf-8",
            )
            multistep_baseline.write_text(
                json.dumps(
                    {
                        "stage_2_unlock_pct": 100.0,
                        "stage_2_focus_pct": 100.0,
                        "stage_1_revisit_after_unlock_count": 0,
                        "stage_2_resolution_count": 1,
                        "scenario_fail_breakdown": {"infra": 0, "llm_patch_drift": 0},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    os.environ.get("PYTHON", "python3"),
                    "-m",
                    "gateforge.agent_modelica_release_preflight_v0_1_3_evidence",
                    "--summary",
                    str(summary_path),
                    "--robustness-baseline-summary",
                    str(robustness_baseline),
                    "--robustness-deterministic-summary",
                    str(robustness_deterministic),
                    "--multistep-baseline-summary",
                    str(multistep_baseline),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("v013_source_blind_robustness_status"), "PASS")
            self.assertEqual(payload.get("v013_source_blind_multistep_status"), "PASS")
            self.assertEqual(float(payload.get("v013_multistep_stage_2_unlock_pct") or 0.0), 100.0)
            self.assertEqual(float(payload.get("v013_multistep_stage_2_focus_pct") or 0.0), 100.0)

    def test_v014_evidence_module_augments_summary(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            summary_path = tmp / "release_preflight_summary.json"
            v4_summary = tmp / "v4_replan.json"
            v5_summary = tmp / "v5_branch.json"

            summary_path.write_text(
                json.dumps({"status": "PASS", "reasons": [], "live_smoke_status": "PASS"}, indent=2),
                encoding="utf-8",
            )
            v4_summary.write_text(
                json.dumps(
                    {
                        "success_count": 6,
                        "total_tasks": 6,
                        "all_scenarios_pass_pct": 100.0,
                        "llm_replan_used_count": 2,
                        "llm_replan_switch_branch_success_count": 2,
                        "branch_selection_error_count": 0,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            v5_summary.write_text(
                json.dumps(
                    {
                        "total_tasks": 6,
                        "all_scenarios_pass_pct": 66.67,
                        "stage_2_branch_pct": 50.0,
                        "llm_request_count_total": 4,
                        "llm_replan_used_count": 2,
                        "first_plan_branch_match_pct": 33.33,
                        "replan_branch_match_pct": 50.0,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    os.environ.get("PYTHON", "python3"),
                    "-m",
                    "gateforge.agent_modelica_release_preflight_v0_1_4_evidence",
                    "--summary",
                    str(summary_path),
                    "--v4-replan-summary",
                    str(v4_summary),
                    "--v5-branch-summary",
                    str(v5_summary),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("v014_v4_llm_replan_status"), "PASS")
            self.assertEqual(payload.get("v014_v5_branch_choice_status"), "PASS")
            self.assertEqual(float(payload.get("v014_v5_stage_2_branch_pct") or 0.0), 50.0)
            self.assertEqual(int(payload.get("v014_v5_llm_replan_used_count") or 0), 2)

    def test_v015_evidence_module_augments_summary(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            summary_path = tmp / "release_preflight_summary.json"
            v4_summary = tmp / "v4_replan.json"
            v5_gemini = tmp / "v5_gemini.json"
            v5_rule = tmp / "v5_rule.json"

            summary_path.write_text(
                json.dumps({"status": "PASS", "reasons": [], "live_smoke_status": "PASS"}, indent=2),
                encoding="utf-8",
            )
            v4_summary.write_text(
                json.dumps(
                    {
                        "success_count": 6,
                        "total_tasks": 6,
                        "all_scenarios_pass_pct": 100.0,
                        "llm_replan_used_count": 2,
                        "llm_replan_switch_branch_success_count": 2,
                        "branch_selection_error_count": 0,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            v5_gemini.write_text(
                json.dumps(
                    {
                        "success_count": 5,
                        "total_tasks": 6,
                        "all_scenarios_pass_pct": 83.33,
                        "stage_2_branch_pct": 50.0,
                        "llm_replan_used_count": 2,
                        "branch_selection_error_count": 1,
                        "first_plan_branch_match_pct": 16.67,
                        "replan_branch_match_pct": 50.0,
                        "llm_guided_search_used_count": 6,
                        "search_budget_followed_count": 6,
                        "llm_budget_helped_resolution_count": 2,
                        "llm_guided_search_resolution_count": 2,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            v5_rule.write_text(
                json.dumps(
                    {
                        "success_count": 2,
                        "total_tasks": 6,
                        "all_scenarios_pass_pct": 33.33,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    os.environ.get("PYTHON", "python3"),
                    "-m",
                    "gateforge.agent_modelica_release_preflight_v0_1_5_evidence",
                    "--summary",
                    str(summary_path),
                    "--v4-replan-summary",
                    str(v4_summary),
                    "--v5-gemini-summary",
                    str(v5_gemini),
                    "--v5-rule-summary",
                    str(v5_rule),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("v015_v4_llm_replan_status"), "PASS")
            self.assertEqual(payload.get("v015_v5_branch_choice_status"), "PASS")
            self.assertEqual(payload.get("v015_v5_guided_search_status"), "PASS")
            self.assertEqual(int(payload.get("v015_v5_success_delta") or 0), 3)
            self.assertEqual(int(payload.get("v015_v5_branch_selection_error_count") or 0), 1)
            self.assertEqual(int(payload.get("v015_v5_llm_guided_search_used_count") or 0), 6)

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
        self.assertIn("ENABLE_L5_EVAL_GATE", script)
        self.assertIn("ENFORCE_L5_EVAL_GATE", script)
        self.assertIn("run_agent_modelica_l5_eval_v1.sh", script)
        self.assertIn('"l5_gate_status"', script)
        self.assertIn('"l5_acceptance_mode"', script)
        self.assertIn('"l5_success_at_k_pct"', script)
        self.assertIn('"l5_delta_success_at_k_pp"', script)
        self.assertIn('"l5_absolute_success_target_pct"', script)
        self.assertIn('"l5_physics_fail_rate_pct"', script)
        self.assertIn('"l5_regression_fail_rate_pct"', script)
        self.assertIn('"l5_infra_failure_count"', script)
        self.assertIn('"l5_non_regression_ok"', script)
        self.assertIn('"l5_primary_reason"', script)

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
                "GATEFORGE_AGENT_RELEASE_ENFORCE_L5_EVAL_GATE": "0",
                "GATEFORGE_AGENT_RELEASE_L5_GATE_MODE": "observe",
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
            self.assertIn(str(summary.get("status") or ""), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(summary.get("live_smoke_status"), "PASS")
            self.assertEqual(summary.get("live_smoke_backend_used"), "mock")
            self.assertEqual(summary.get("l3_diagnostic_gate_status"), "PASS")
            self.assertEqual(float(summary.get("l3_parse_coverage_pct") or 0.0), 100.0)
            self.assertIn(str(summary.get("l5_gate_status") or ""), {"PASS", "NEEDS_REVIEW"})
            self.assertIn("l5_acceptance_mode", summary)
            self.assertIn("l5_success_at_k_pct", summary)
            self.assertIn("l5_delta_success_at_k_pp", summary)
            self.assertIn("l5_absolute_success_target_pct", summary)
            self.assertIn("l5_physics_fail_rate_pct", summary)
            self.assertIn("l5_regression_fail_rate_pct", summary)
            self.assertIn("l5_infra_failure_count", summary)
            self.assertIn("l5_non_regression_ok", summary)
            self.assertIn("l5_primary_reason", summary)

            l5_summary = json.loads((out_dir / "l5_eval_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("l5_primary_reason") or "none"), str(l5_summary.get("primary_reason") or "none"))
            self.assertEqual(
                str(summary.get("l5_acceptance_mode") or "delta_uplift"),
                str(l5_summary.get("acceptance_mode") or "delta_uplift"),
            )


if __name__ == "__main__":
    unittest.main()
