import re
import unittest
from pathlib import Path


class CIShardConfigContractTests(unittest.TestCase):
    def test_test_sharded_matrix_and_artifact_name_contract(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        pairs = re.findall(r'- pattern: "([^"]+)"\n\s+shard: "([^"]+)"', workflow)
        self.assertEqual(
            pairs,
            [
                ("test_[a-h]*.py", "a-h"),
                ("test_[i-p]*.py", "i-p"),
                ("test_[q-z]*.py", "q-z"),
            ],
            msg="test-sharded matrix must define stable pattern/shard pairs",
        )

        self.assertIn('name: unittest-shard-logs-${{ matrix.shard }}', workflow)
        self.assertNotIn('name: unittest-shard-logs-${{ matrix.pattern }}', workflow)
        self.assertIn('scripts/ci_run_unittest_shard.sh "${{ matrix.pattern }}"', workflow)
        self.assertIn('if-no-files-found: ignore', workflow)


if __name__ == "__main__":
    unittest.main()
