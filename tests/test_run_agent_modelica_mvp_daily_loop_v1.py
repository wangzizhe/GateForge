import unittest
from pathlib import Path


class RunAgentModelicaMvpDailyLoopV1Tests(unittest.TestCase):
    def test_script_wires_daily_run_and_periodic_ab_checkpoint(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_mvp_daily_loop_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("GATEFORGE_AGENT_RETRIEVAL_AB_INTERVAL", content)
        self.assertIn("scripts/run_agent_modelica_weekly_chain_v1.sh", content)
        self.assertIn("scripts/run_agent_modelica_retrieval_ab_checkpoint_v1.sh", content)
        self.assertIn("GATEFORGE_AGENT_HOLDOUT_CHECKPOINT_INTERVAL", content)
        self.assertIn("scripts/run_agent_modelica_holdout_checkpoint_v1.sh", content)
        self.assertIn("gateforge.agent_modelica_mvp_checkpoint_gate_v1", content)
        self.assertIn("AB_RC", content)
        self.assertIn("HOLDOUT_RC", content)
        self.assertIn("CHECKPOINT_RC", content)
        self.assertIn("ROLLING_FOCUS_TARGETS_PATH", content)
        self.assertIn("ROLLING_FOCUS_ENABLE", content)
        self.assertIn("ROLLING_FOCUS_MAX_AGE_RUNS", content)
        self.assertIn("ROLLING_FOCUS_DECAY", content)
        self.assertIn("ROLLING_FOCUS_MAX_ENTRIES", content)
        self.assertIn("CHECKPOINT_MIN_FOCUS_HIT_RATE_PCT", content)
        self.assertIn("CHECKPOINT_MAX_FOCUS_MISS_RATE_PCT", content)
        self.assertIn("GATEFORGE_AGENT_FOCUS_TARGETS_PATH", content)
        self.assertIn("focus_targets_in_path", content)
        self.assertIn("focus_targets_out_path", content)
        self.assertIn("focus_hit_rate_pct", content)
        self.assertIn("focus_hit_failed_task_count", content)
        self.assertIn("--daily-focus-hit-rate-pct", content)
        self.assertIn("median_repair_rounds", content)
        self.assertIn("ab_execution_rc", content)
        self.assertIn("holdout_execution_rc", content)
        self.assertIn("checkpoint_execution_rc", content)
        self.assertIn("history.jsonl", content)


if __name__ == "__main__":
    unittest.main()
