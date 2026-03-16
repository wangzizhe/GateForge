import unittest
from pathlib import Path


class RunAgentModelicaWave21Smoke3LiveScriptV1Tests(unittest.TestCase):
    def test_script_contains_expected_dynamic_task_ids(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_wave2_1_smoke3_live_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("wave2_1_buildings_loads_solver_sensitive_simulate_failure", content)
        self.assertIn("wave2_1_ibpsa_acsimplegrid_event_logic_error", content)
        self.assertIn("wave2_1_transform_integratorwithreset_semantic_drift_after_compile_pass", content)


if __name__ == "__main__":
    unittest.main()
