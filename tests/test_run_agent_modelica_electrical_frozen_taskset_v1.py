import unittest
from pathlib import Path


class RunAgentModelicaElectricalFrozenTasksetV1Tests(unittest.TestCase):
    def test_script_wires_expand_and_split_freeze(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_electrical_frozen_taskset_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("--expand-failure-types", content)
        self.assertIn("agent_modelica_taskset_split_freeze_v1", content)
        self.assertIn("--out-taskset \"$OUT_DIR/taskset_frozen.json\"", content)
        self.assertIn("split_counts", content)


if __name__ == "__main__":
    unittest.main()
