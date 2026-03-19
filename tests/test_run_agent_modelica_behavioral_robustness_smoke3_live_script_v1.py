import unittest
from pathlib import Path


class RunAgentModelicaBehavioralRobustnessSmoke3LiveScriptV1Tests(unittest.TestCase):
    def test_script_contains_smoke3_robustness_selection(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_behavioral_robustness_smoke3_live_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("param_perturbation_robustness_violation", content)
        self.assertIn("initial_condition_robustness_violation", content)
        self.assertIn("scenario_switch_robustness_violation", content)
        self.assertIn("agent_modelica_behavioral_robustness_taskset_v1", content)


if __name__ == "__main__":
    unittest.main()
