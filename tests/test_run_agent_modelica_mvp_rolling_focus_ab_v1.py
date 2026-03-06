import unittest
from pathlib import Path


class RunAgentModelicaMvpRollingFocusAbV1Tests(unittest.TestCase):
    def test_script_wires_on_off_daily_loop_compare(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_mvp_rolling_focus_ab_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("scripts/run_agent_modelica_mvp_daily_loop_v1.sh", content)
        self.assertIn("GATEFORGE_AGENT_MVP_DAILY_ROLLING_FOCUS_ENABLE", content)
        self.assertIn("compare.json", content)
        self.assertIn("delta_on_minus_off", content)
        self.assertIn("focus_hit_rate_pct", content)
        self.assertIn("physics_fail_count", content)
        self.assertIn("median_repair_rounds", content)


if __name__ == "__main__":
    unittest.main()
