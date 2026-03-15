import unittest
from pathlib import Path


class CIShardConfigContractTests(unittest.TestCase):
    def test_core_dataset_smoke_and_demo_full_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn('env:\n  CI_TIMEOUT_CORE: "20m"\n  CI_TIMEOUT_DATASET: "25m"\n  CI_TIMEOUT_DEMO_FULL: "45m"', workflow)
        self.assertIn('  test-core-a:\n    name: "Test Core A"', workflow)
        self.assertIn('  test-core-b:\n    name: "Test Core B"', workflow)
        self.assertIn('  test-dataset:\n    name: "Test Dataset"', workflow)
        self.assertIn('  fast-check-gate:\n    name: "Fast Checks"', workflow)
        self.assertIn('  release-preflight:\n    name: "Release Preflight"', workflow)
        self.assertIn('  l3-diagnostic-gate:\n    name: "L3 Diagnostic Gate"', workflow)
        self.assertIn('  l5-gate:\n    name: "L5 Gate"', workflow)
        self.assertIn('  l5-nightly-observe:\n    name: "L5 Nightly Observe"', workflow)
        self.assertIn('  l4-nightly-observe:\n    name: "L4 Nightly Observe"', workflow)
        self.assertIn('  smoke-gate:\n    name: "Smoke"', workflow)
        self.assertIn('  test-and-smoke:\n    name: "Test and Smoke"', workflow)
        self.assertIn('  demo-full:\n    name: "Demo Full"', workflow)
        self.assertIn('CI_FAIL_ON_EMPTY_PATTERN: "1"', workflow)

        self.assertIn(
            'scripts/ci_run_unittest_shard.sh "test_[a-c]*.py,test_[e-i]*.py"',
            workflow,
        )
        self.assertIn(
            'scripts/ci_run_unittest_shard.sh "test_demo_bundle.py,test_demo_runtime_contract.py,test_[j-q]*.py,test_r[!u]*.py,test_runtime_*.py,test_run.py,test_run_[!p]*.py,test_s*.py"',
            workflow,
        )
        self.assertIn(
            'scripts/ci_run_unittest_shard.sh "test_dataset_[a-m]*.py,test_dataset_[n-z]*.py"',
            workflow,
        )
        self.assertIn('scripts/ci_run_unittest_shard.sh "test_demo_scripts.py"', workflow)
        self.assertIn("needs:\n      - test-core-a\n      - test-core-b\n      - test-dataset", workflow)
        self.assertIn(
            "needs:\n      - test-core-a\n      - test-core-b\n      - test-dataset\n      - fast-check-gate\n      - smoke-gate",
            workflow,
        )
        self.assertIn("bash scripts/run_agent_modelica_electrical_realism_frozen_taskset_v1.sh", workflow)
        self.assertIn("bash scripts/run_agent_modelica_connector_fast_check_v1.sh", workflow)
        self.assertIn("bash scripts/run_agent_modelica_underconstrained_fast_check_v1.sh", workflow)
        self.assertIn("bash scripts/run_agent_modelica_release_preflight_v0_1_2.sh", workflow)
        self.assertIn("bash scripts/run_agent_modelica_l3_stability_regression_v0.sh", workflow)
        self.assertIn("bash scripts/run_agent_modelica_l5_eval_v1.sh", workflow)
        self.assertIn('run_release_live_smoke:', workflow)
        self.assertIn("Publish release preflight status", workflow)
        self.assertIn("artifacts/release_v0_1_2/release_preflight_summary.json", workflow)
        self.assertIn("l3_diagnostic_gate_status", workflow)
        self.assertIn("l3_parse_coverage_pct", workflow)
        self.assertIn("l3_type_match_rate_pct", workflow)
        self.assertIn("l3_stage_match_rate_pct", workflow)
        self.assertIn("l5_gate_status", workflow)
        self.assertIn("l5_acceptance_mode", workflow)
        self.assertIn("l5_success_at_k_pct", workflow)
        self.assertIn("l5_delta_success_at_k_pp", workflow)
        self.assertIn("l5_absolute_success_target_pct", workflow)
        self.assertIn("l5_physics_fail_rate_pct", workflow)
        self.assertIn("l5_regression_fail_rate_pct", workflow)
        self.assertIn("l5_infra_failure_count", workflow)
        self.assertIn("l5_non_regression_ok", workflow)
        self.assertIn("l5_primary_reason", workflow)
        self.assertIn("artifacts/agent_modelica_l3_stability_regression_v0_ci", workflow)
        self.assertIn("artifacts/agent_modelica_l5_eval_v1_ci", workflow)
        self.assertIn("artifacts/agent_modelica_l5_eval_v1_nightly", workflow)
        self.assertIn("artifacts/agent_modelica_l4_closed_loop_v0_nightly", workflow)
        self.assertIn("artifacts/agent_modelica_electrical_realism_frozen_taskset_v1_ci", workflow)
        self.assertIn("artifacts/agent_modelica_connector_fast_check_v1_ci", workflow)
        self.assertIn("artifacts/agent_modelica_underconstrained_fast_check_v1_ci", workflow)
        self.assertIn("tests/fixtures/agent_modelica_l4_challenge_taskset_v0.json", workflow)
        self.assertIn("artifacts/private/l5_eval_ledger_v1.jsonl", workflow)
        self.assertIn("tests/fixtures/agent_modelica_l3_stability_ci_taskset_v0.json", workflow)
        self.assertIn("python3 -m gateforge.agent_modelica_live_executor_mock_v0", workflow)
        self.assertIn("python3 -m gateforge.agent_modelica_live_executor_mock_l4_switch_v0", workflow)
        self.assertIn("inputs.run_release_live_smoke", workflow)
        self.assertIn("if: ${{ github.event_name == 'schedule' }}", workflow)
        self.assertIn('GATEFORGE_AGENT_L5_EVAL_PLANNER_BACKEND: "gemini"', workflow)
        self.assertIn('GATEFORGE_AGENT_L4_CLOSED_LOOP_PLANNER_BACKEND: "gemini"', workflow)
        self.assertIn('GATEFORGE_AGENT_L4_MIN_SUCCESS_DELTA_PP: "0"', workflow)
        self.assertIn("bash scripts/run_agent_modelica_l4_closed_loop_v0.sh", workflow)
        self.assertIn(
            "if: ${{ (github.event_name == 'workflow_dispatch' && inputs.run_demo_bundle) || github.event_name == 'schedule' }}",
            workflow,
        )
        self.assertIn("id: demo_full_tests", workflow)
        self.assertIn("Publish demo full status", workflow)
        self.assertIn("steps.demo_full_tests.outcome", workflow)
        self.assertIn("continue-on-error: ${{ github.event_name == 'pull_request' }}", workflow)
        self.assertIn("needs.fast-check-gate.result", workflow)
        self.assertIn("needs.l3-diagnostic-gate.result", workflow)
        self.assertIn("needs.l5-gate.result", workflow)
        self.assertIn('if-no-files-found: ignore', workflow)


if __name__ == "__main__":
    unittest.main()
