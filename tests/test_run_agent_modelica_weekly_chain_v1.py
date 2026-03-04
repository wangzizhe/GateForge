import unittest
from pathlib import Path


class RunAgentModelicaWeeklyChainV1Tests(unittest.TestCase):
    def test_weekly_chain_uses_private_repair_history_default(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_weekly_chain_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn(
            'REPAIR_HISTORY_PATH="${GATEFORGE_AGENT_REPAIR_HISTORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"',
            content,
        )
        self.assertIn("python3 -m gateforge.agent_modelica_repair_memory_store_v1", content)

    def test_layered_baseline_script_uses_private_repair_history_default(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_layered_baseline_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn(
            'REPAIR_HISTORY="${GATEFORGE_AGENT_LAYERED_BASELINE_REPAIR_HISTORY:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"',
            content,
        )


if __name__ == "__main__":
    unittest.main()
