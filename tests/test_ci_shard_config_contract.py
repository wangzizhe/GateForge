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
        self.assertIn('  smoke-gate:\n    name: "Smoke"', workflow)
        self.assertIn('  test-and-smoke:\n    name: "Test and Smoke"', workflow)
        self.assertIn('  demo-full:\n    name: "Demo Full"', workflow)

        self.assertIn(
            'scripts/ci_run_unittest_shard.sh "test_[a-c]*.py,test_[e-i]*.py"',
            workflow,
        )
        self.assertIn(
            'scripts/ci_run_unittest_shard.sh "test_d[!ae]*.py,test_demo_bundle.py,test_demo_runtime_contract.py,test_[j-z]*.py"',
            workflow,
        )
        self.assertIn(
            'scripts/ci_run_unittest_shard.sh "test_dataset_[a-m]*.py,test_dataset_[n-z]*.py"',
            workflow,
        )
        self.assertIn('scripts/ci_run_unittest_shard.sh "test_demo_scripts.py"', workflow)
        self.assertIn("needs:\n      - test-core-a\n      - test-core-b\n      - test-dataset", workflow)
        self.assertIn("needs:\n      - test-core-a\n      - test-core-b\n      - test-dataset\n      - smoke-gate", workflow)
        self.assertIn(
            "if: ${{ (github.event_name == 'workflow_dispatch' && inputs.run_demo_full) || github.event_name == 'schedule' }}",
            workflow,
        )
        self.assertIn("id: demo_full_tests", workflow)
        self.assertIn("Publish demo full status", workflow)
        self.assertIn("steps.demo_full_tests.outcome", workflow)
        self.assertIn('if-no-files-found: ignore', workflow)


if __name__ == "__main__":
    unittest.main()
