import unittest
from pathlib import Path


class RunAgentModelicaWave2Smoke3LiveScriptV1Tests(unittest.TestCase):
    def test_script_wires_three_task_wave2_smoke_chain(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_wave2_smoke3_live_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_wave2_realism_taskset_v1", content)
        self.assertIn("agent_modelica_unknown_library_smoke_taskset_v1", content)
        self.assertIn("agent_modelica_unknown_library_smoke3_summary_v1", content)
        self.assertIn("--mode live", content)
        self.assertIn("baseline_off_live", content)
        self.assertNotIn("retrieval_on_live", content)
        self.assertIn("GATEFORGE_AGENT_WAVE2_SMOKE_TASK_IDS", content)
        self.assertIn("wave2_buildings_loads_overconstrained_system", content)
        self.assertIn("__SOURCE_LIBRARY_PATH__", content)


if __name__ == "__main__":
    unittest.main()
