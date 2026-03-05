import unittest
from pathlib import Path


class RunAgentModelicaWeeklyChainV1Tests(unittest.TestCase):
    def test_weekly_chain_supports_mvp_profile_mapping(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_weekly_chain_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('MVP_PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/agent_modelica_mvp_repair_v1.json}"', content)
        self.assertIn("--max-rounds \"$MAX_ROUNDS\"", content)
        self.assertIn("--runtime-threshold \"$RUNTIME_THRESHOLD\"", content)
        self.assertIn("--persistence-weight \"$FOCUS_PERSISTENCE_WEIGHT\"", content)
        self.assertIn("--strategy-signal-weight \"$FOCUS_SIGNAL_WEIGHT\"", content)
        self.assertIn("--strategy-signal-target-score \"$FOCUS_SIGNAL_TARGET_SCORE\"", content)
        self.assertIn("--inject-hard-fail-count \"$INJECT_HARD_FAIL_COUNT\"", content)
        self.assertIn("--inject-slow-pass-count \"$INJECT_SLOW_PASS_COUNT\"", content)
        self.assertIn('ALLOW_BASELINE_FAIL="${GATEFORGE_AGENT_ALLOW_BASELINE_FAIL:-0}"', content)
        self.assertIn("gateforge.agent_modelica_focus_template_bundle_v1", content)

    def test_weekly_chain_uses_private_repair_history_default(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_weekly_chain_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn(
            'REPAIR_HISTORY_PATH="${GATEFORGE_AGENT_REPAIR_HISTORY_PATH:-${PROFILE_REPAIR_HISTORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}}"',
            content,
        )
        self.assertIn("python3 -m gateforge.agent_modelica_repair_memory_store_v1", content)

    def test_layered_baseline_script_uses_private_repair_history_default(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_layered_baseline_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn(
            'REPAIR_HISTORY="${GATEFORGE_AGENT_LAYERED_BASELINE_REPAIR_HISTORY:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}"',
            content,
        )


if __name__ == "__main__":
    unittest.main()
