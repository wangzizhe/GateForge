import unittest
from pathlib import Path


class CIShardConfigContractTests(unittest.TestCase):
    def test_public_core_workflow_runs_only_sanitized_tests(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("public-core:", workflow)
        self.assertIn("python -m unittest", workflow)
        self.assertIn("tests.test_agent_modelica_workspace_style_probe_v0_67", workflow)
        self.assertIn("tests.test_agent_modelica_omc_workspace_v1", workflow)
        self.assertNotIn("assets_private", workflow)


if __name__ == "__main__":
    unittest.main()
