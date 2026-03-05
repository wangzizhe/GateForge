import unittest
from pathlib import Path


class RunAgentModelicaMvpDailyLoopV1Tests(unittest.TestCase):
    def test_script_wires_daily_run_and_periodic_ab_checkpoint(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_mvp_daily_loop_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("GATEFORGE_AGENT_RETRIEVAL_AB_INTERVAL", content)
        self.assertIn("scripts/run_agent_modelica_weekly_chain_v1.sh", content)
        self.assertIn("scripts/run_agent_modelica_retrieval_ab_checkpoint_v1.sh", content)
        self.assertIn("GATEFORGE_AGENT_HOLDOUT_CHECKPOINT_INTERVAL", content)
        self.assertIn("scripts/run_agent_modelica_holdout_checkpoint_v1.sh", content)
        self.assertIn("gateforge.agent_modelica_mvp_checkpoint_gate_v1", content)
        self.assertIn("AB_RC", content)
        self.assertIn("HOLDOUT_RC", content)
        self.assertIn("CHECKPOINT_RC", content)
        self.assertIn("ab_execution_rc", content)
        self.assertIn("holdout_execution_rc", content)
        self.assertIn("checkpoint_execution_rc", content)
        self.assertIn("history.jsonl", content)


if __name__ == "__main__":
    unittest.main()
