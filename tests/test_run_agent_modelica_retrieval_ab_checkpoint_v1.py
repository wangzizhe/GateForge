import unittest
from pathlib import Path


class RunAgentModelicaRetrievalAbCheckpointV1Tests(unittest.TestCase):
    def test_script_wires_off_on_runs_and_summary_output(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_retrieval_ab_checkpoint_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("ab_off_", content)
        self.assertIn("ab_on_", content)
        self.assertIn("GATEFORGE_AGENT_ALLOW_BASELINE_FAIL", content)
        self.assertIn("ab_summary.json", content)
        self.assertIn("delta_on_minus_off", content)


if __name__ == "__main__":
    unittest.main()
