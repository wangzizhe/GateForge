import unittest
from pathlib import Path


class RunAgentModelicaV034SingleCaseRuleprioCheckScriptTests(unittest.TestCase):
    def test_script_enables_multi_round_deterministic_repair_and_targets_ibpsa_case(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_v0_3_4_single_case_ruleprio_check.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR=1", content)
        self.assertIn("multi_round_ibpsa_acsimplegrid_coupled_conflict_failure_v034_ruleprio", content)
        self.assertIn("coupled_conflict_failure", content)
        self.assertIn("agent_modelica_live_executor_v1", content)
        self.assertIn("--planner-backend gemini", content)


if __name__ == "__main__":
    unittest.main()
