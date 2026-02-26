import re
import unittest
from pathlib import Path


class DemoRuntimeContractTests(unittest.TestCase):
    def test_demo_tests_with_subprocess_run_define_timeout(self) -> None:
        tests_dir = Path(__file__).resolve().parent
        demo_tests = sorted(tests_dir.glob("test_*demo*.py"))
        self.assertTrue(demo_tests, "expected demo tests to exist")

        missing_timeout = []
        run_pattern = re.compile(r"subprocess\.run\(")
        timeout_pattern = re.compile(r"timeout\s*=\s*\d+")

        for test_file in demo_tests:
            if test_file.name == Path(__file__).name:
                continue
            content = test_file.read_text(encoding="utf-8")
            if run_pattern.search(content) and not timeout_pattern.search(content):
                missing_timeout.append(test_file.name)

        self.assertFalse(
            missing_timeout,
            msg=(
                "demo tests that invoke subprocess.run must include timeout to avoid CI hangs: "
                + ", ".join(missing_timeout)
            ),
        )


if __name__ == "__main__":
    unittest.main()
