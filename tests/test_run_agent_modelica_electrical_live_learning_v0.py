import unittest
from pathlib import Path


class RunAgentModelicaElectricalLiveLearningV0Tests(unittest.TestCase):
    def test_script_wires_live_learning_chain(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_electrical_live_learning_v0.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_electrical_mutant_taskset_v0", content)
        self.assertIn("--mode live", content)
        self.assertIn("agent_modelica_run_contract_v1", content)
        self.assertIn("agent_modelica_repair_memory_store_v1", content)
        self.assertIn("agent_modelica_repair_capability_learner_v1", content)
        self.assertIn("agent_modelica_diagnostic_quality_v0", content)
        self.assertIn("--mutation-style \"$MUTATION_STYLE\"", content)
        self.assertIn("--repair-actions __REPAIR_ACTIONS_SHQ__", content)
        self.assertIn("GATEFORGE_AGENT_LIVE_PLANNER_BACKEND:-gemini", content)


if __name__ == "__main__":
    unittest.main()
