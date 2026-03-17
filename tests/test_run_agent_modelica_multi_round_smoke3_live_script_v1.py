import unittest
from pathlib import Path


class RunAgentModelicaMultiRoundSmoke3LiveScriptV1Tests(unittest.TestCase):
    def test_script_contains_auto_selection_logic(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_multi_round_smoke3_live_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("resolve_smoke_task_ids", content)
        self.assertIn("selected_libraries", content)
        self.assertIn("selected_models", content)
        self.assertIn("source_rewrite_count", content)


if __name__ == "__main__":
    unittest.main()
