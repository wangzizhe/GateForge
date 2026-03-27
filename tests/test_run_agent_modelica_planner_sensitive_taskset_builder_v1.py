from pathlib import Path
import unittest


class RunAgentModelicaPlannerSensitiveTasksetBuilderV1ScriptTests(unittest.TestCase):
    def test_script_calls_module(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_planner_sensitive_taskset_builder_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("gateforge.agent_modelica_planner_sensitive_taskset_builder_v1", content)
        self.assertIn("GATEFORGE_AGENT_PLANNER_SENSITIVE_TASKSET_RESULTS", content)


if __name__ == "__main__":
    unittest.main()
