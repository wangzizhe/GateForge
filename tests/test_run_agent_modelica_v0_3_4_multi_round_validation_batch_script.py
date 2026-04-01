from __future__ import annotations

import unittest
from pathlib import Path


class RunAgentModelicaV034MultiRoundValidationBatchScriptTests(unittest.TestCase):
    def test_script_uses_current_workorder_and_enables_multi_round_deterministic_repair(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "run_agent_modelica_v0_3_4_multi_round_validation_batch.sh"
        content = script_path.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_multi_round_validation_workorder_v0_3_4_current/summary.json", content)
        self.assertIn("taskset_candidates_refreshed.json", content)
        self.assertIn("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR=1", content)
        self.assertIn("python3 -m gateforge.agent_modelica_live_executor_gemini_v1", content)


if __name__ == "__main__":
    unittest.main()
