import unittest
from pathlib import Path


class RunAgentModelicaHoldoutCheckpointV1Tests(unittest.TestCase):
    def test_script_wires_holdout_builder_and_layered_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_holdout_checkpoint_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("gateforge.agent_modelica_holdout_taskset_builder_v1", content)
        self.assertIn("gateforge.agent_modelica_layered_baseline_v1", content)
        self.assertIn("GATEFORGE_AGENT_HOLDOUT_EXCLUDE_TASKSET", content)
        self.assertIn("holdout_taskset.json", content)


if __name__ == "__main__":
    unittest.main()
