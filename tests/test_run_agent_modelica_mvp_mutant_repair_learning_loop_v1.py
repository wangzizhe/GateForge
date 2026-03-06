import unittest
from pathlib import Path


class RunAgentModelicaMvpMutantRepairLearningLoopV1Tests(unittest.TestCase):
    def test_script_wires_weekly_holdout_and_compare(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_mvp_mutant_repair_learning_loop_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("run_agent_modelica_weekly_chain_v1.sh", content)
        self.assertIn("run_agent_modelica_holdout_checkpoint_v1.sh", content)
        self.assertIn("mutant_recipe_lock.json", content)
        self.assertIn("focus_targets_path", content)
        self.assertIn("summary.json", content)

    def test_script_uses_private_learning_asset_defaults(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_mvp_mutant_repair_learning_loop_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn(
            'REPAIR_HISTORY_PATH="${GATEFORGE_AGENT_REPAIR_HISTORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"',
            content,
        )
        self.assertIn(
            'PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}"',
            content,
        )
        self.assertIn(
            'RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}"',
            content,
        )


if __name__ == "__main__":
    unittest.main()
