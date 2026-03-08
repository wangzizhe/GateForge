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
        self.assertIn('  release-preflight:\n    name: "Release Preflight"', workflow)
        self.assertIn('  l3-diagnostic-gate:\n    name: "L3 Diagnostic Gate"', workflow)
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
        self.assertIn("needs:\n      - test-core-a\n      - test-core-b\n      - test-dataset\n      - smoke-gate", workflow)
        self.assertIn("bash scripts/run_agent_modelica_release_preflight_v0_1_1.sh", workflow)
        self.assertIn("bash scripts/run_agent_modelica_l3_stability_regression_v0.sh", workflow)
        self.assertIn('run_release_live_smoke:', workflow)
        self.assertIn("Publish release preflight status", workflow)
        self.assertIn("artifacts/release_v0_1_1/release_preflight_summary.json", workflow)
        self.assertIn("l3_diagnostic_gate_status", workflow)
        self.assertIn("l3_parse_coverage_pct", workflow)
        self.assertIn("l3_type_match_rate_pct", workflow)
        self.assertIn("l3_stage_match_rate_pct", workflow)
        self.assertIn("artifacts/agent_modelica_l3_stability_regression_v0_ci", workflow)
        self.assertIn("tests/fixtures/agent_modelica_l3_stability_ci_taskset_v0.json", workflow)
        self.assertIn("python3 -m gateforge.agent_modelica_live_executor_mock_v0", workflow)
        self.assertIn("inputs.run_release_live_smoke", workflow)
        self.assertIn(
            "if: ${{ (github.event_name == 'workflow_dispatch' && inputs.run_demo_bundle) || github.event_name == 'schedule' }}",
            workflow,
        )
        self.assertIn("id: demo_full_tests", workflow)
        self.assertIn("Publish demo full status", workflow)
        self.assertIn("steps.demo_full_tests.outcome", workflow)
        self.assertIn("continue-on-error: ${{ github.event_name == 'pull_request' }}", workflow)
        self.assertIn("needs.l3-diagnostic-gate.result", workflow)
        self.assertIn('if-no-files-found: ignore', workflow)


if __name__ == "__main__":
    unittest.main()
