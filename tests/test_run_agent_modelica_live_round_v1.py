import unittest
from pathlib import Path


class RunAgentModelicaLiveRoundV1Tests(unittest.TestCase):
    def test_script_requires_live_executor_and_calls_weekly_chain_live_mode(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_live_round_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-}"', content)
        self.assertIn("missing GATEFORGE_AGENT_LIVE_EXECUTOR_CMD for live mode", content)
        self.assertIn('GATEFORGE_AGENT_RUN_MODE="live"', content)
        self.assertIn("bash scripts/run_agent_modelica_weekly_chain_v1.sh", content)


if __name__ == "__main__":
    unittest.main()
