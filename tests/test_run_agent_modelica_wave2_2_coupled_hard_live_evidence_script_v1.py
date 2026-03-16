import unittest
from pathlib import Path


class RunAgentModelicaWave22CoupledHardLiveEvidenceScriptV1Tests(unittest.TestCase):
    def test_script_contains_coupled_hard_stages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_wave2_2_coupled_hard_live_evidence_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_wave2_2_coupled_hard_taskset_v1", content)
        self.assertIn("deterministic_on_live", content)
        self.assertIn("GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR=1", content)
        self.assertIn("task_construction_still_too_easy", content)
        self.assertIn("easy_task_exclusions.json", content)
        self.assertIn("latest_decision_summary.json", content)


if __name__ == "__main__":
    unittest.main()
