import unittest
from pathlib import Path


class RunAgentModelicaMvpExecSummaryV1Tests(unittest.TestCase):
    def test_script_calls_exec_summary_module(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_mvp_exec_summary_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("gateforge.agent_modelica_mvp_exec_summary_v1", content)
        self.assertIn("--three-round-summary", content)
        self.assertIn("--retrieval-ab-summary", content)
        self.assertIn("--challenge-compare", content)


if __name__ == "__main__":
    unittest.main()
