import unittest
from pathlib import Path


class RunAgentModelicaMutantRecipeLockV1Tests(unittest.TestCase):
    def test_script_wires_recipe_lock_and_taskset_outputs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_mutant_recipe_lock_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('RECIPE_LOCK_PATH="${GATEFORGE_AGENT_RECIPE_LOCK_PATH:-benchmarks/agent_modelica_mutant_recipe_lock_v1.json}"', content)
        self.assertIn("gateforge.agent_modelica_hardpack_taskset_builder_v1", content)
        self.assertIn("taskset_${SNAPSHOT_TAG}.json", content)
        self.assertIn("recipe_lock_${SNAPSHOT_TAG}.json", content)
        self.assertIn("agent_modelica_mutant_recipe_lock_v1_execution", content)


if __name__ == "__main__":
    unittest.main()
