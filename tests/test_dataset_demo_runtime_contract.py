import re
import unittest
from pathlib import Path


class DatasetDemoRuntimeContractTests(unittest.TestCase):
    def test_dataset_demo_tests_have_timeout_and_fast_mode(self) -> None:
        tests_dir = Path(__file__).resolve().parent
        demo_tests = sorted(tests_dir.glob("test_dataset_*_demo.py"))
        self.assertTrue(demo_tests, "expected dataset demo tests to exist")

        missing_timeout = []
        missing_fast_mode = []

        for test_file in demo_tests:
            content = test_file.read_text(encoding="utf-8")
            if not re.search(r"timeout\s*=\s*\d+", content):
                missing_timeout.append(test_file.name)
            if '"GATEFORGE_DEMO_FAST": "1"' not in content:
                missing_fast_mode.append(test_file.name)

        self.assertFalse(
            missing_timeout,
            msg=(
                "dataset demo tests must define subprocess timeout to avoid CI hangs: "
                + ", ".join(missing_timeout)
            ),
        )
        self.assertFalse(
            missing_fast_mode,
            msg=(
                "dataset demo tests must set GATEFORGE_DEMO_FAST=1 to keep CI fast: "
                + ", ".join(missing_fast_mode)
            ),
        )


if __name__ == "__main__":
    unittest.main()
