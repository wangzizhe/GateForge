import unittest
from pathlib import Path


class RunAgentModelicaSourceBlindMultistepSmoke3LiveScriptV1Tests(unittest.TestCase):
    def test_script_contains_multistep_smoke_selection(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        content = (repo_root / "scripts" / "run_agent_modelica_source_blind_multistep_smoke3_live_v1.sh").read_text(encoding="utf-8")
        self.assertIn("stability_then_behavior", content)
        self.assertIn("behavior_then_robustness", content)
        self.assertIn("switch_then_recovery", content)
        self.assertIn('preferred_model_by_failure', content)
        self.assertIn('"plant_b"', content)
        self.assertIn('"switch_b"', content)
        self.assertIn('"hybrid_b"', content)
        self.assertIn("agent_modelica_source_blind_multistep_taskset_v1", content)
        self.assertIn("GATEFORGE_AGENT_SOURCE_BLIND_MULTISTEP_SMOKE3_DETERMINISTIC_REPAIR", content)
        self.assertIn("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR=1", content)


if __name__ == "__main__":
    unittest.main()
