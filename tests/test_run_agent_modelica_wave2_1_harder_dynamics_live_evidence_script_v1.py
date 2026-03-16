import unittest
from pathlib import Path


class RunAgentModelicaWave21HarderDynamicsLiveEvidenceScriptV1Tests(unittest.TestCase):
    def test_script_contains_dynamic_stages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_wave2_1_harder_dynamics_live_evidence_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_wave2_1_harder_dynamics_taskset_v1", content)
        self.assertIn("deterministic_on_live", content)
        self.assertIn("GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR=1", content)
        self.assertIn("agent_modelica_wave2_1_evidence_v1", content)
        self.assertIn("latest_decision_summary.json", content)


if __name__ == "__main__":
    unittest.main()
