import unittest
from pathlib import Path


class CIShardConfigContractTests(unittest.TestCase):
    def test_public_test_suite_uses_safe_runtime_checks(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("public-test-suite:", workflow)
        self.assertIn('python-version: ["3.10", "3.11", "3.12"]', workflow)
        self.assertIn("python -m compileall gateforge tests scripts", workflow)
        self.assertIn("python -m unittest", workflow)
        self.assertIn("tests.test_agent_modelica_workspace_style_probe_v0_67", workflow)
        self.assertIn("tests.test_agent_modelica_omc_workspace_v1", workflow)
        self.assertIn("task_[0-9]{3,}", workflow)
        self.assertNotIn("v0.138", workflow)
        self.assertNotIn("v0.139", workflow)


if __name__ == "__main__":
    unittest.main()
