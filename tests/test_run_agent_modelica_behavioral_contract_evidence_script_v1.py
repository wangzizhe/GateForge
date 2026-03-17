import unittest
from pathlib import Path


class RunAgentModelicaBehavioralContractEvidenceScriptV1Tests(unittest.TestCase):
    def test_script_contains_behavioral_stages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_behavioral_contract_evidence_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_behavioral_contract_taskset_v1", content)
        self.assertIn("agent_modelica_behavioral_contract_baseline_summary_v1", content)
        self.assertIn("agent_modelica_behavioral_contract_evidence_v1", content)
        self.assertIn("RETRIEVAL_MODE", content)
        self.assertIn("mode_transition", content)


if __name__ == "__main__":
    unittest.main()
