import unittest
from pathlib import Path


class RunAgentModelicaBehavioralContractLiveEvidenceScriptV1Tests(unittest.TestCase):
    def test_script_contains_live_behavioral_stages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_behavioral_contract_live_evidence_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_behavioral_contract_taskset_v1", content)
        self.assertIn("agent_modelica_behavioral_contract_baseline_summary_v1", content)
        self.assertIn("agent_modelica_behavioral_contract_evidence_v1", content)
        self.assertIn("GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_DETERMINISTIC_REPAIR=1", content)
        self.assertIn("CONTRACT_PASS_TOO_EASY_THRESHOLD_PCT", content)


if __name__ == "__main__":
    unittest.main()
