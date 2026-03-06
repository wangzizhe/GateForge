import unittest
from pathlib import Path


class RunAgentModelicaWeeklyChainV1Tests(unittest.TestCase):
    def test_weekly_chain_supports_mvp_profile_mapping(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_weekly_chain_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('DEFAULT_MVP_PROFILE_PATH="benchmarks/agent_modelica_mvp_repair_v1.json"', content)
        self.assertIn('if [ -f "benchmarks/private/agent_modelica_mvp_repair_v1.json" ]; then', content)
        self.assertIn('MVP_PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-$DEFAULT_MVP_PROFILE_PATH}"', content)
        self.assertIn('DEFAULT_PHYSICS_CONTRACT_PATH="policies/physics_contract_v0.json"', content)
        self.assertIn('if [ -f "policies/private/physics_contract_v0.json" ]; then', content)
        self.assertIn('PHYSICS_CONTRACT="${GATEFORGE_AGENT_PHYSICS_CONTRACT:-$DEFAULT_PHYSICS_CONTRACT_PATH}"', content)
        self.assertIn('DEFAULT_HARDPACK_PATH="benchmarks/agent_modelica_hardpack_v1.json"', content)
        self.assertIn('if [ -f "benchmarks/private/agent_modelica_hardpack_v1.json" ]; then', content)
        self.assertIn('HARDPACK_PATH="${GATEFORGE_AGENT_HARDPACK_PATH:-${PROFILE_HARDPACK_PATH:-$DEFAULT_HARDPACK_PATH}}"', content)
        self.assertIn("--max-rounds \"$MAX_ROUNDS\"", content)
        self.assertIn("--runtime-threshold \"$RUNTIME_THRESHOLD\"", content)
        self.assertIn("--persistence-weight \"$FOCUS_PERSISTENCE_WEIGHT\"", content)
        self.assertIn("--strategy-signal-weight \"$FOCUS_SIGNAL_WEIGHT\"", content)
        self.assertIn("--strategy-signal-target-score \"$FOCUS_SIGNAL_TARGET_SCORE\"", content)
        self.assertIn("--inject-hard-fail-count \"$INJECT_HARD_FAIL_COUNT\"", content)
        self.assertIn("--inject-slow-pass-count \"$INJECT_SLOW_PASS_COUNT\"", content)
        self.assertIn('ALLOW_BASELINE_FAIL="${GATEFORGE_AGENT_ALLOW_BASELINE_FAIL:-0}"', content)
        self.assertIn("gateforge.agent_modelica_focus_template_bundle_v1", content)
        self.assertIn('LIVE_EXECUTOR_CMD="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-}"', content)
        self.assertIn("--live-timeout-sec \"$LIVE_TIMEOUT_SEC\"", content)
        self.assertIn("--live-max-output-chars \"$LIVE_MAX_OUTPUT_CHARS\"", content)
        self.assertIn('PREFLIGHT_ENABLE="${GATEFORGE_AGENT_PREFLIGHT_ENABLE:-1}"', content)
        self.assertIn("gateforge.agent_modelica_learning_preflight_v1", content)
        self.assertIn("gateforge.agent_modelica_taskset_split_freeze_v1", content)
        self.assertIn("gateforge.agent_modelica_run_snapshot_v1", content)
        self.assertIn("gateforge.agent_modelica_first_failure_attribution_v1", content)
        self.assertIn("gateforge.agent_modelica_script_parse_focus_taskset_v1", content)
        self.assertIn('SCRIPT_PARSE_FOCUS_MIN_TASKS="${GATEFORGE_AGENT_SCRIPT_PARSE_FOCUS_MIN_TASKS:-3}"', content)
        self.assertIn('SCRIPT_PARSE_FOCUS_MAX_TASKS="${GATEFORGE_AGENT_SCRIPT_PARSE_FOCUS_MAX_TASKS:-6}"', content)
        self.assertIn("--run-records-jsonl \"$RUN_RECORDS_JSONL\"", content)
        self.assertIn("--resume-run-contract", content)

    def test_weekly_chain_uses_private_repair_history_default(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_weekly_chain_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn(
            'REPAIR_HISTORY_PATH="${GATEFORGE_AGENT_REPAIR_HISTORY_PATH:-${PROFILE_REPAIR_HISTORY_PATH:-data/private_failure_corpus/agent_modelica_repair_memory_v1.json}}"',
            content,
        )
        self.assertIn("python3 -m gateforge.agent_modelica_repair_memory_store_v1", content)
        self.assertIn(
            'PATCH_TEMPLATE_ADAPTATIONS_PATH="${GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH:-${PROFILE_PATCH_TEMPLATE_ADAPTATIONS_PATH:-data/private_failure_corpus/agent_modelica_patch_template_adaptations_v1.json}}"',
            content,
        )
        self.assertIn(
            'RETRIEVAL_POLICY_PATH="${GATEFORGE_AGENT_RETRIEVAL_POLICY_PATH:-${PROFILE_RETRIEVAL_POLICY_PATH:-data/private_failure_corpus/agent_modelica_retrieval_policy_v1.json}}"',
            content,
        )
        self.assertIn("python3 -m gateforge.agent_modelica_repair_capability_learner_v1", content)

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
