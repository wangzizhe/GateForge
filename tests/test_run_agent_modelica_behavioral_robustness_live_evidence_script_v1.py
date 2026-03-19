import unittest
from pathlib import Path


class RunAgentModelicaBehavioralRobustnessLiveEvidenceScriptV1Tests(unittest.TestCase):
    def test_script_contains_live_robustness_stages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_behavioral_robustness_live_evidence_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_behavioral_robustness_taskset_v1", content)
        self.assertIn("agent_modelica_behavioral_robustness_baseline_summary_v1", content)
        self.assertIn("agent_modelica_behavioral_robustness_evidence_v1", content)
        self.assertIn("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR=1", content)


if __name__ == "__main__":
    unittest.main()
