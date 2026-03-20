import unittest
from pathlib import Path


class RunAgentModelicaSourceBlindMultistepLiveEvidenceScriptV1Tests(unittest.TestCase):
    def test_script_contains_multistep_live_stages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        content = (repo_root / "scripts" / "run_agent_modelica_source_blind_multistep_live_evidence_v1.sh").read_text(encoding="utf-8")
        self.assertIn("agent_modelica_source_blind_multistep_taskset_v1", content)
        self.assertIn("agent_modelica_source_blind_multistep_baseline_summary_v1", content)
        self.assertIn("agent_modelica_source_blind_multistep_evidence_v1", content)
        self.assertIn("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR=1", content)
        self.assertIn('STOP_AFTER_STAGE" = "deterministic_on_live"', content)


if __name__ == "__main__":
    unittest.main()
