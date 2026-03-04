import unittest
from pathlib import Path


class RunAgentModelicaMvpBeforeAfterV1Tests(unittest.TestCase):
    def test_script_wires_before_after_focus_loop(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_mvp_before_after_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("scripts/run_agent_modelica_weekly_chain_v1.sh", content)
        self.assertIn("GATEFORGE_AGENT_FOCUS_TARGETS_PATH", content)
        self.assertIn("FOCUS_QUEUE_PATH", content)
        self.assertIn("compare.json", content)
        self.assertIn("delta_success_at_k_pct", content)


if __name__ == "__main__":
    unittest.main()
