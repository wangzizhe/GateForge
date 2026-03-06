import unittest
from pathlib import Path


class RunAgentModelicaLiveRoundV1Tests(unittest.TestCase):
    def test_script_sets_default_live_executor_and_calls_weekly_chain_live_mode(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_live_round_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('DEFAULT_PROFILE_PATH="benchmarks/agent_modelica_mvp_repair_v1.json"', content)
        self.assertIn('if [ -f "benchmarks/private/agent_modelica_mvp_repair_v1.json" ]; then', content)
        self.assertIn('PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-$DEFAULT_PROFILE_PATH}"', content)
        self.assertIn('DEFAULT_LIVE_EXECUTOR_CMD="python3 -m gateforge.agent_modelica_live_executor_gemini_v1', content)
        self.assertIn("GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-gemini", content)
        self.assertIn('LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-$DEFAULT_LIVE_EXECUTOR_CMD}"', content)
        self.assertIn('GATEFORGE_AGENT_RUN_MODE="live"', content)
        self.assertIn("bash scripts/run_agent_modelica_weekly_chain_v1.sh", content)


if __name__ == "__main__":
    unittest.main()
