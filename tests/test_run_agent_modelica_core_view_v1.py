import unittest
from pathlib import Path


class RunAgentModelicaCoreViewV1Tests(unittest.TestCase):
    def test_script_wires_core_scope_snapshot_module(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_core_view_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("gateforge.agent_modelica_core_scope_snapshot_v1", content)
        self.assertIn('SCOPE_PATH="${GATEFORGE_AGENT_CORE_SCOPE_PATH:-core/agent_modelica/core_scope_v1.json}"', content)
        self.assertIn("--out \"$OUT_DIR/snapshot.json\"", content)
        self.assertIn("--report-out \"$OUT_DIR/snapshot.md\"", content)


if __name__ == "__main__":
    unittest.main()
