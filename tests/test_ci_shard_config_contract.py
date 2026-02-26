import unittest
from pathlib import Path


class CIShardConfigContractTests(unittest.TestCase):
    def test_core_dataset_smoke_and_demo_full_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn('  test-core:\n    name: "Test Core"', workflow)
        self.assertIn('  test-dataset:\n    name: "Test Dataset"', workflow)
        self.assertIn('  smoke-gate:\n    name: "Smoke"', workflow)
        self.assertIn('  test-and-smoke:\n    name: "Test and Smoke"', workflow)
        self.assertIn('  demo-full:\n    name: "Demo Full"', workflow)

        self.assertIn(
            'scripts/ci_run_unittest_shard.sh "test_[a-c]*.py,test_d[!ae]*.py,test_demo_bundle.py,test_demo_runtime_contract.py,test_[e-z]*.py"',
            workflow,
        )
        self.assertIn(
            'scripts/ci_run_unittest_shard.sh "test_dataset_[a-m]*.py,test_dataset_[n-z]*.py"',
            workflow,
        )
        self.assertIn('scripts/ci_run_unittest_shard.sh "test_demo_scripts.py"', workflow)
        self.assertIn("needs:\n      - test-core\n      - test-dataset\n      - smoke-gate", workflow)
        self.assertIn(
            "if: ${{ (github.event_name == 'workflow_dispatch' && inputs.run_demo_full) || github.event_name == 'schedule' }}",
            workflow,
        )
        self.assertIn('if-no-files-found: ignore', workflow)


if __name__ == "__main__":
    unittest.main()
