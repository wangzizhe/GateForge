import unittest
from pathlib import Path


class RunAgentModelicaWave22Smoke3LiveScriptV1Tests(unittest.TestCase):
    def test_script_contains_auto_selection_logic(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_wave2_2_smoke3_live_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("resolve_smoke_task_ids", content)
        self.assertIn("repair_triviality_risk", content)
        self.assertIn("source_dependency_count", content)
        self.assertIn("failure_signal_delay_sec", content)
        self.assertIn("selected_libraries", content)
        self.assertIn("selected_models", content)
        self.assertIn("library_key", content)
        self.assertIn("model_key", content)


if __name__ == "__main__":
    unittest.main()
