import unittest
from pathlib import Path


class RunAgentModelicaLearningAssetRefreshV1Tests(unittest.TestCase):
    def test_script_wires_backfill_then_capability_refresh(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_learning_asset_refresh_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('REPAIR_MEMORY_PATH="${GATEFORGE_AGENT_REPAIR_MEMORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"', content)
        self.assertIn("agent_modelica_repair_memory_backfill_v1", content)
        self.assertIn("--memory-out \"$REPAIR_MEMORY_PATH\"", content)
        self.assertIn("agent_modelica_repair_capability_learner_v1", content)
        self.assertIn("--out-retrieval-policy \"$RETRIEVAL_POLICY_PATH\"", content)
        self.assertIn("--out-patch-template-adaptations \"$PATCH_TEMPLATE_ADAPTATIONS_PATH\"", content)


if __name__ == "__main__":
    unittest.main()
