import re
import unittest
from pathlib import Path


class CIShardConfigContractTests(unittest.TestCase):
    def test_test_sharded_matrix_and_artifact_name_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        pairs = re.findall(r'- patterns: "([^"]+)"\n\s+shard: "([^"]+)"', workflow)
        self.assertEqual(
            pairs,
            [
                ("test_[a-c]*.py,test_d[!ae]*.py,test_demo_bundle.py,test_demo_runtime_contract.py,test_[e-i]*.py", "core-a-i"),
                ("test_demo_scripts.py", "demo-scripts"),
                ("test_[j-z]*.py", "core-j-z"),
                ("test_dataset_[a-m]*.py", "dataset-a-m"),
                ("test_dataset_[n-z]*.py", "dataset-n-z"),
            ],
            msg="test-sharded matrix must define stable pattern/shard pairs",
        )

        self.assertIn('name: unittest-shard-logs-${{ matrix.shard }}', workflow)
        self.assertNotIn('name: unittest-shard-logs-${{ matrix.pattern }}', workflow)
        self.assertIn('scripts/ci_run_unittest_shard.sh "${{ matrix.patterns }}"', workflow)
        self.assertIn('if-no-files-found: ignore', workflow)


if __name__ == "__main__":
    unittest.main()
