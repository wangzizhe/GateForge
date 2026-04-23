"""Tests for agent_modelica_l2_plan_replan_engine_v1.

Covers pure-function logic that does not require LLM calls or network access:
- parse_env_assignment
- bootstrap_env_from_repo (env isolation)
- resolve_llm_provider (env-based routing)
- behavioral_robustness_source_mode
- planner_family_for_provider / planner_adapter_for_provider
- build_source_blind_multistep_planner_contract
- llm_round_constraints
- Adapter Unification: gemini/openai wrappers delegate to llm_repair_model_text
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_l2_plan_replan_engine_v1 import (
    MULTISTEP_PLANNER_CONTRACT_VERSION,
    behavioral_robustness_source_mode,
    bootstrap_env_from_repo,
    build_source_blind_multistep_planner_contract,
    build_source_blind_multistep_planner_prompt,
    gemini_repair_model_text,
    llm_round_constraints,
    openai_repair_model_text,
    parse_env_assignment,
    planner_adapter_for_provider,
    planner_family_for_provider,
    resolve_llm_provider,
)


class TestParseEnvAssignment(unittest.TestCase):
    def test_plain_key_value(self) -> None:
        self.assertEqual(parse_env_assignment("FOO=bar"), ("FOO", "bar"))

    def test_export_prefix_stripped(self) -> None:
        self.assertEqual(parse_env_assignment("export FOO=bar"), ("FOO", "bar"))

    def test_double_quoted_value(self) -> None:
        k, v = parse_env_assignment('KEY="hello world"')
        self.assertEqual(k, "KEY")
        self.assertEqual(v, "hello world")

    def test_single_quoted_value(self) -> None:
        k, v = parse_env_assignment("KEY='val'")
        self.assertEqual(k, "KEY")
        self.assertEqual(v, "val")

    def test_comment_line_returns_none(self) -> None:
        self.assertEqual(parse_env_assignment("# comment"), (None, None))

    def test_blank_line_returns_none(self) -> None:
        self.assertEqual(parse_env_assignment(""), (None, None))

    def test_no_equals_returns_none(self) -> None:
        self.assertEqual(parse_env_assignment("NOEQUALS"), (None, None))

    def test_invalid_key_returns_none(self) -> None:
        self.assertEqual(parse_env_assignment("1INVALID=val"), (None, None))


class TestBootstrapEnvFromRepo(unittest.TestCase):
    def test_loads_key_from_cwd_env_file(self) -> None:
        prev = os.environ.get("GATEFORGE_TEST_BOOTSTRAP_KEY")
        os.environ.pop("GATEFORGE_TEST_BOOTSTRAP_KEY", None)
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / ".env"
            env_file.write_text("GATEFORGE_TEST_BOOTSTRAP_KEY=loaded_value\n", encoding="utf-8")
            old_cwd = os.getcwd()
            try:
                os.chdir(td)
                count = bootstrap_env_from_repo(allowed_keys={"GATEFORGE_TEST_BOOTSTRAP_KEY"})
                self.assertGreaterEqual(count, 1)
                self.assertEqual(os.environ.get("GATEFORGE_TEST_BOOTSTRAP_KEY"), "loaded_value")
            finally:
                os.chdir(old_cwd)
                if prev is None:
                    os.environ.pop("GATEFORGE_TEST_BOOTSTRAP_KEY", None)
                else:
                    os.environ["GATEFORGE_TEST_BOOTSTRAP_KEY"] = prev

    def test_skips_already_set_key(self) -> None:
        prev = os.environ.get("GATEFORGE_TEST_ALREADY_SET")
        os.environ["GATEFORGE_TEST_ALREADY_SET"] = "original"
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / ".env"
            env_file.write_text("GATEFORGE_TEST_ALREADY_SET=overwrite\n", encoding="utf-8")
            old_cwd = os.getcwd()
            try:
                os.chdir(td)
                bootstrap_env_from_repo(allowed_keys={"GATEFORGE_TEST_ALREADY_SET"})
                self.assertEqual(os.environ.get("GATEFORGE_TEST_ALREADY_SET"), "original")
            finally:
                os.chdir(old_cwd)
                if prev is None:
                    os.environ.pop("GATEFORGE_TEST_ALREADY_SET", None)
                else:
                    os.environ["GATEFORGE_TEST_ALREADY_SET"] = prev


class TestResolveLlmProvider(unittest.TestCase):
    def _clear_provider_env(self) -> dict:
        keys = ["GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY",
                "DASHSCOPE_API_KEY", "QWEN_API_KEY", "DASHSCOPE_BASE_URL",
                "MINIMAX_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "LLM_MODEL", "GATEFORGE_GEMINI_MODEL", "GEMINI_MODEL",
                "OPENAI_MODEL", "QWEN_MODEL", "MINIMAX_MODEL", "LLM_PROVIDER", "GATEFORGE_LIVE_PLANNER_BACKEND"]
        prev = {k: os.environ.get(k) for k in keys}
        for k in keys:
            os.environ.pop(k, None)
        return prev

    def _restore_env(self, prev: dict) -> None:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_rule_backend_returns_rule(self) -> None:
        prev = self._clear_provider_env()
        try:
            with patch("gateforge.agent_modelica_l2_plan_replan_engine_v1.bootstrap_env_from_repo", return_value=0):
                provider, model, key = resolve_llm_provider("rule")
            self.assertEqual(provider, "rule")
            self.assertEqual(model, "")
            self.assertEqual(key, "")
        finally:
            self._restore_env(prev)

    def test_explicit_openai_backend_selected(self) -> None:
        prev = self._clear_provider_env()
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["LLM_MODEL"] = "gpt-4o"
        try:
            with patch("gateforge.agent_modelica_l2_plan_replan_engine_v1.bootstrap_env_from_repo", return_value=0):
                provider, model, key = resolve_llm_provider("openai")
            self.assertEqual(provider, "openai")
            self.assertEqual(key, "sk-test")
        finally:
            self._restore_env(prev)

    def test_infers_openai_from_gpt_model_name(self) -> None:
        prev = self._clear_provider_env()
        os.environ["OPENAI_API_KEY"] = "sk-abc"
        os.environ["LLM_MODEL"] = "gpt-4"
        try:
            with patch("gateforge.agent_modelica_l2_plan_replan_engine_v1.bootstrap_env_from_repo", return_value=0):
                provider, model, key = resolve_llm_provider("auto")
            self.assertEqual(provider, "openai")
            self.assertEqual(model, "gpt-4")
            self.assertEqual(key, "sk-abc")
        finally:
            self._restore_env(prev)

    def test_explicit_minimax_backend_selected(self) -> None:
        prev = self._clear_provider_env()
        os.environ["MINIMAX_API_KEY"] = "mm-key"
        os.environ["LLM_MODEL"] = "MiniMax-M2.7"
        try:
            with patch("gateforge.agent_modelica_l2_plan_replan_engine_v1.bootstrap_env_from_repo", return_value=0):
                provider, model, key = resolve_llm_provider("minimax")
            self.assertEqual(provider, "minimax")
            self.assertEqual(model, "MiniMax-M2.7")
            self.assertEqual(key, "mm-key")
        finally:
            self._restore_env(prev)

    def test_explicit_minimax_backend_accepts_anthropic_compat_key(self) -> None:
        prev = self._clear_provider_env()
        os.environ["ANTHROPIC_API_KEY"] = "anth-mm-key"
        os.environ["ANTHROPIC_BASE_URL"] = "https://api.minimaxi.com/anthropic"
        os.environ["LLM_MODEL"] = "MiniMax-M2.7"
        try:
            with patch("gateforge.agent_modelica_l2_plan_replan_engine_v1.bootstrap_env_from_repo", return_value=0):
                provider, model, key = resolve_llm_provider("minimax")
            self.assertEqual(provider, "minimax")
            self.assertEqual(model, "MiniMax-M2.7")
            self.assertEqual(key, "anth-mm-key")
        finally:
            self._restore_env(prev)

    def test_explicit_qwen_backend_selected(self) -> None:
        prev = self._clear_provider_env()
        os.environ["DASHSCOPE_API_KEY"] = "dashscope-key"
        os.environ["LLM_MODEL"] = "qwen3.6-flash"
        try:
            with patch("gateforge.agent_modelica_l2_plan_replan_engine_v1.bootstrap_env_from_repo", return_value=0):
                provider, model, key = resolve_llm_provider("qwen")
            self.assertEqual(provider, "qwen")
            self.assertEqual(model, "qwen3.6-flash")
            self.assertEqual(key, "dashscope-key")
        finally:
            self._restore_env(prev)

    def test_infers_qwen_from_model_name(self) -> None:
        prev = self._clear_provider_env()
        os.environ["QWEN_API_KEY"] = "qwen-key"
        os.environ["LLM_MODEL"] = "qwen3.6-flash"
        try:
            with patch("gateforge.agent_modelica_l2_plan_replan_engine_v1.bootstrap_env_from_repo", return_value=0):
                provider, model, key = resolve_llm_provider("auto")
            self.assertEqual(provider, "qwen")
            self.assertEqual(model, "qwen3.6-flash")
            self.assertEqual(key, "qwen-key")
        finally:
            self._restore_env(prev)

    def test_missing_model_raises_even_when_provider_key_exists(self) -> None:
        prev = self._clear_provider_env()
        os.environ["GOOGLE_API_KEY"] = "google-key"
        try:
            with patch("gateforge.agent_modelica_l2_plan_replan_engine_v1.bootstrap_env_from_repo", return_value=0):
                with self.assertRaisesRegex(ValueError, "missing_llm_model"):
                    resolve_llm_provider("auto")
        finally:
            self._restore_env(prev)


class TestBehavioralRobustnessSourceMode(unittest.TestCase):
    def test_default_is_source_aware(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE")
        os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE", None)
        try:
            self.assertEqual(behavioral_robustness_source_mode(), "source_aware")
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = prev

    def test_blind_alias_returns_source_blind(self) -> None:
        for value in ("blind", "source_blind", "source-blind"):
            with self.subTest(value=value):
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = value
                self.assertEqual(behavioral_robustness_source_mode(), "source_blind")
        os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE", None)


class TestPlannerFamilyAndAdapter(unittest.TestCase):
    def test_rule_family(self) -> None:
        self.assertEqual(planner_family_for_provider("rule"), "rule")

    def test_gemini_family(self) -> None:
        self.assertEqual(planner_family_for_provider("gemini"), "llm")

    def test_openai_family(self) -> None:
        self.assertEqual(planner_family_for_provider("openai"), "llm")

    def test_minimax_family(self) -> None:
        self.assertEqual(planner_family_for_provider("minimax"), "llm")

    def test_qwen_family(self) -> None:
        self.assertEqual(planner_family_for_provider("qwen"), "llm")

    def test_unknown_family(self) -> None:
        self.assertEqual(planner_family_for_provider("mystery"), "unknown")

    def test_gemini_adapter(self) -> None:
        self.assertEqual(planner_adapter_for_provider("gemini"), "gateforge_gemini_planner_v1")

    def test_openai_adapter(self) -> None:
        self.assertEqual(planner_adapter_for_provider("openai"), "gateforge_openai_planner_v1")

    def test_minimax_adapter(self) -> None:
        self.assertEqual(planner_adapter_for_provider("minimax"), "gateforge_minimax_planner_v1")

    def test_qwen_adapter(self) -> None:
        self.assertEqual(planner_adapter_for_provider("qwen"), "gateforge_qwen_planner_v1")

    def test_rule_adapter(self) -> None:
        self.assertEqual(planner_adapter_for_provider("rule"), "gateforge_rule_planner_v1")

    def test_unknown_provider_adapter(self) -> None:
        self.assertEqual(planner_adapter_for_provider("mystery"), "gateforge_unknown_planner_v1")


class TestBuildPlannerContract(unittest.TestCase):
    def test_schema_version_matches_constant(self) -> None:
        contract = build_source_blind_multistep_planner_contract(
            resolved_provider="gemini",
            request_kind="plan",
            stage_context={"current_stage": "stage_1", "stage_2_branch": ""},
            llm_reason="initial_plan",
        )
        self.assertEqual(contract["schema_version"], MULTISTEP_PLANNER_CONTRACT_VERSION)

    def test_rule_provider_maps_to_rule_family(self) -> None:
        contract = build_source_blind_multistep_planner_contract(
            resolved_provider="rule",
            request_kind="plan",
            stage_context={},
            llm_reason="rule_only",
        )
        self.assertEqual(contract["planner_family"], "rule")

    def test_stage_context_fields_extracted(self) -> None:
        ctx = {
            "current_stage": "stage_2",
            "stage_2_branch": "plantb",
            "preferred_stage_2_branch": "plantb",
            "current_fail_bucket": "behavior",
            "branch_mode": "bifurcation",
            "trap_branch": True,
        }
        contract = build_source_blind_multistep_planner_contract(
            resolved_provider="gemini",
            request_kind="replan",
            stage_context=ctx,
            llm_reason="replan_trigger",
        )
        self.assertEqual(contract["current_stage"], "stage_2")
        self.assertEqual(contract["current_branch"], "plantb")
        self.assertTrue(contract["trap_branch"])

    def test_replan_count_defaults_zero(self) -> None:
        contract = build_source_blind_multistep_planner_contract(
            resolved_provider="gemini",
            request_kind="plan",
            stage_context={},
            llm_reason="",
        )
        self.assertEqual(contract["replan_count_before"], 0)

    def test_prompt_includes_planner_experience_summary_and_hints(self) -> None:
        prompt, contract = build_source_blind_multistep_planner_prompt(
            original_text="model Demo end Demo;",
            failure_type="model_check_error",
            expected_stage="check",
            error_excerpt="some error",
            repair_actions=["repair|parse_error_pre_repair|rule_engine_v1"],
            model_name="Demo",
            current_round=1,
            stage_context={"current_stage": "stage_1"},
            llm_reason="initial_plan",
            request_kind="plan",
            replan_context=None,
            resolved_provider="gemini",
            planner_experience_context={
                "used": True,
                "positive_hint_count": 1,
                "caution_hint_count": 1,
                "prompt_token_estimate": 42,
                "truncated": False,
                "prompt_context_text": (
                    "Historical experience hints for similar failures:\n"
                    "- Historical success: parse_error_pre_repair advanced similar repairs.\n"
                    "- Historical caution: multi_round_layered_repair regressed similar repairs.\n"
                ),
            },
        )
        self.assertEqual(contract["schema_version"], MULTISTEP_PLANNER_CONTRACT_VERSION)
        self.assertIn("planner_experience_summary", prompt)
        self.assertIn("Historical success", prompt)
        self.assertIn("Historical caution", prompt)


class TestLlmRoundConstraints(unittest.TestCase):
    def test_no_constraints_for_unknown_failure(self) -> None:
        result = llm_round_constraints(failure_type="unknown_type", current_round=1)
        self.assertEqual(result, "")

    def test_robustness_constraints_returned(self) -> None:
        result = llm_round_constraints(
            failure_type="param_perturbation_robustness_violation",
            current_round=1,
        )
        self.assertIn("behavioral robustness task", result)

    def test_round_1_extra_constraint_for_robustness(self) -> None:
        result = llm_round_constraints(
            failure_type="param_perturbation_robustness_violation",
            current_round=1,
        )
        self.assertIn("round 1", result)

    def test_round_2_no_round_1_constraint(self) -> None:
        result = llm_round_constraints(
            failure_type="param_perturbation_robustness_violation",
            current_round=2,
        )
        self.assertNotIn("round 1", result)

    def test_cascading_failure_round_1_constraint(self) -> None:
        result = llm_round_constraints(
            failure_type="cascading_structural_failure",
            current_round=1,
        )
        self.assertIn("multi-round repair task", result)

    def test_cascading_failure_round_2_empty(self) -> None:
        result = llm_round_constraints(
            failure_type="cascading_structural_failure",
            current_round=2,
        )
        self.assertEqual(result, "")


class TestAdapterUnification(unittest.TestCase):
    """Verify the Adapter Unification Pattern: gemini/openai wrappers delegate
    to llm_repair_model_text rather than duplicating prompt construction."""

    def test_gemini_wrapper_calls_llm_repair_model_text(self) -> None:
        """gemini_repair_model_text returns (patched, err) without provider field."""
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            return_value=("patched_text", "", "gemini"),
        ) as mock_unified:
            patched, err = gemini_repair_model_text(
                original_text="model M end M;",
                failure_type="param_perturbation_robustness_violation",
                expected_stage="simulate",
                error_excerpt="",
                repair_actions=[],
                model_name="M",
            )
        mock_unified.assert_called_once()
        call_kwargs = mock_unified.call_args.kwargs
        self.assertEqual(call_kwargs["planner_backend"], "gemini")
        self.assertIsNone(call_kwargs.get("repair_history"))
        self.assertEqual(patched, "patched_text")
        self.assertEqual(err, "")

    def test_openai_wrapper_calls_llm_repair_model_text(self) -> None:
        """openai_repair_model_text returns (patched, err) without provider field."""
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            return_value=(None, "openai_missing_patched_model_text", "openai"),
        ) as mock_unified:
            patched, err = openai_repair_model_text(
                original_text="model M end M;",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="some error",
                repair_actions=["fix x"],
                model_name="M",
            )
        mock_unified.assert_called_once()
        call_kwargs = mock_unified.call_args.kwargs
        self.assertEqual(call_kwargs["planner_backend"], "openai")
        self.assertIsNone(call_kwargs.get("repair_history"))
        self.assertIsNone(patched)
        self.assertEqual(err, "openai_missing_patched_model_text")

    def test_gemini_wrapper_propagates_error(self) -> None:
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            return_value=(None, "gemini_api_key_missing", "gemini"),
        ):
            patched, err = gemini_repair_model_text(
                original_text="model M end M;",
                failure_type="param_perturbation_robustness_violation",
                expected_stage="simulate",
                error_excerpt="",
                repair_actions=[],
                model_name="M",
            )
        self.assertIsNone(patched)
        self.assertEqual(err, "gemini_api_key_missing")


class TestToolContextPrompting(unittest.TestCase):
    def test_llm_repair_prompt_includes_tool_context_when_present(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text
        from gateforge.llm_provider_adapter import LLMProviderConfig

        class DummyAdapter:
            pass

        captured: dict[str, str] = {}

        def fake_send(adapter, prompt, config):
            captured["prompt"] = prompt
            return ('{"patched_model_text":"model M end M;","rationale":"ok"}', "")

        with patch(
            "gateforge.llm_provider_adapter.resolve_provider_adapter",
            return_value=(
                DummyAdapter(),
                LLMProviderConfig(provider_name="gemini", model="gemini-test", api_key="key"),
            ),
        ), patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.send_with_budget",
            side_effect=fake_send,
        ):
            patched, err, provider = llm_repair_model_text(
                planner_backend="gemini",
                original_text="model M end M;",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="omc output",
                repair_actions=[],
                model_name="M",
                tool_context="=== modelica_query_tool_observations ===\nvariable: x",
            )

        self.assertEqual(patched, "model M end M;")
        self.assertEqual(err, "")
        self.assertEqual(provider, "gemini")
        self.assertIn("modelica_query_tool_observations", captured["prompt"])
        self.assertIn("Tool observations from local Modelica query APIs", captured["prompt"])

    def test_llm_repair_model_text_multi_forwards_tool_context(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi

        calls: list[dict] = []

        def fake(**kwargs):
            calls.append(kwargs)
            return ("model X end X;", "", "gemini")

        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            side_effect=fake,
        ):
            llm_repair_model_text_multi(
                planner_backend="gemini",
                original_text="model X end X;",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="omc",
                repair_actions=[],
                model_name="X",
                tool_context="tool facts",
                num_candidates=2,
                inter_call_delay_s=0.0,
                retry_backoff_s=0.0,
            )

        self.assertEqual(len(calls), 2)
        self.assertEqual([call["tool_context"] for call in calls], ["tool facts", "tool facts"])




class TestFormatRepairHistory(unittest.TestCase):
    """Unit tests for _format_repair_history."""

    def test_empty_history_returns_empty_string(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _format_repair_history
        self.assertEqual(_format_repair_history(None), "")
        self.assertEqual(_format_repair_history([]), "")

    def test_single_entry_formatted(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _format_repair_history
        history = [
            {
                "round": 1,
                "model_changed": True,
                "check_pass": False,
                "omc_summary": "12 equations, 15 variables (deficit: 3)",
                "change_summary": "You added equation(s).",
            }
        ]
        result = _format_repair_history(history)
        self.assertIn("=== Previous Repair Attempts ===", result)
        self.assertIn("Attempt 1 (Round 1):", result)
        self.assertIn("You added equation(s).", result)
        self.assertIn("checkModel FAILED", result)
        self.assertIn("12 equations, 15 variables (deficit: 3)", result)
        self.assertIn("===============================", result)

    def test_multiple_entries_numbered(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _format_repair_history
        history = [
            {
                "round": 1,
                "model_changed": True,
                "check_pass": False,
                "omc_summary": "eq=12, var=15",
                "change_summary": "You removed declaration(s).",
            },
            {
                "round": 2,
                "model_changed": True,
                "check_pass": True,
                "omc_summary": "eq=15, var=15",
                "change_summary": "You added equation(s).",
            },
        ]
        result = _format_repair_history(history)
        self.assertIn("Attempt 1 (Round 1):", result)
        self.assertIn("Attempt 2 (Round 2):", result)
        self.assertIn("checkModel FAILED", result)
        self.assertIn("checkModel PASSED", result)

    def test_no_change_shows_stall(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _format_repair_history
        history = [
            {
                "round": 1,
                "model_changed": False,
                "check_pass": False,
                "omc_summary": "",
                "change_summary": "",
            }
        ]
        result = _format_repair_history(history)
        self.assertIn("You made no changes.", result)


class TestResolveTemperatureSchedule(unittest.TestCase):
    def test_n1_default_matches_provider_config_default(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _resolve_temperature_schedule
        from gateforge.llm_provider_adapter import LLMProviderConfig
        # N=1 baseline must exactly reproduce historical single-call temperature
        # so v0.19.51 baseline is strictly comparable to v0.19.49/50 baseline.
        self.assertEqual(_resolve_temperature_schedule(1, None), [LLMProviderConfig.temperature])
        self.assertEqual(_resolve_temperature_schedule(1, None), [0.1])

    def test_n3_default_slice(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _resolve_temperature_schedule
        self.assertEqual(_resolve_temperature_schedule(3, None), [0.1, 0.4, 0.7])

    def test_n5_default_full(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _resolve_temperature_schedule
        self.assertEqual(_resolve_temperature_schedule(5, None), [0.1, 0.4, 0.7, 0.4, 0.1])

    def test_n7_cycles(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _resolve_temperature_schedule
        sched = _resolve_temperature_schedule(7, None)
        self.assertEqual(len(sched), 7)
        self.assertEqual(sched[:5], [0.1, 0.4, 0.7, 0.4, 0.1])
        self.assertEqual(sched[5:], [0.1, 0.4])

    def test_explicit_schedule_used(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _resolve_temperature_schedule
        self.assertEqual(
            _resolve_temperature_schedule(3, [0.1, 0.3, 0.9]),
            [0.1, 0.3, 0.9],
        )

    def test_explicit_length_mismatch_raises(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _resolve_temperature_schedule
        with self.assertRaises(ValueError):
            _resolve_temperature_schedule(3, [0.1, 0.3])

    def test_zero_returns_empty(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _resolve_temperature_schedule
        self.assertEqual(_resolve_temperature_schedule(0, None), [])


class TestLLMRepairModelTextMulti(unittest.TestCase):
    def test_invalid_num_candidates_raises(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
        with self.assertRaises(ValueError):
            llm_repair_model_text_multi(
                planner_backend="gemini",
                original_text="model X end X;",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="",
                repair_actions=[],
                model_name="X",
                num_candidates=0,
            )

    def test_n1_makes_one_call_with_temperature_0_1(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
        calls: list[dict] = []
        def fake(**kwargs):
            calls.append(kwargs)
            return ("model X patched end X;", "", "gemini")
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            side_effect=fake,
        ):
            results = llm_repair_model_text_multi(
                planner_backend="gemini",
                original_text="model X end X;",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="some omc text",
                repair_actions=[],
                model_name="X",
                num_candidates=1,
                inter_call_delay_s=0.0,
                retry_backoff_s=0.0,
            )
        self.assertEqual(len(results), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["temperature_override"], 0.1)
        self.assertEqual(results[0]["candidate_id"], 0)
        self.assertEqual(results[0]["temperature_used"], 0.1)
        self.assertEqual(results[0]["patched_text"], "model X patched end X;")

    def test_n3_uses_default_schedule_and_indexes_candidates(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
        calls: list[dict] = []
        def fake(**kwargs):
            calls.append(kwargs)
            return (f"patched_{kwargs['temperature_override']}", "", "gemini")
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            side_effect=fake,
        ):
            results = llm_repair_model_text_multi(
                planner_backend="gemini",
                original_text="x",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="",
                repair_actions=[],
                model_name="X",
                num_candidates=3,
                inter_call_delay_s=0.0,
                retry_backoff_s=0.0,
            )
        self.assertEqual([c["temperature_override"] for c in calls], [0.1, 0.4, 0.7])
        self.assertEqual([r["candidate_id"] for r in results], [0, 1, 2])
        self.assertEqual([r["temperature_used"] for r in results], [0.1, 0.4, 0.7])

    def test_failed_llm_call_keeps_row_with_none_text(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
        def fake(**kwargs):
            if kwargs["temperature_override"] == 0.4:
                return (None, "rate_limit", "gemini")
            return ("ok", "", "gemini")
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            side_effect=fake,
        ):
            results = llm_repair_model_text_multi(
                planner_backend="gemini",
                original_text="x",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="",
                repair_actions=[],
                model_name="X",
                num_candidates=3,
                inter_call_delay_s=0.0,
                retry_backoff_s=0.0,
                retry_on_error=False,
            )
        self.assertEqual(len(results), 3)
        self.assertEqual(results[1]["patched_text"], None)
        self.assertEqual(results[1]["llm_error"], "rate_limit")
        self.assertEqual(results[0]["patched_text"], "ok")
        self.assertEqual(results[2]["patched_text"], "ok")

    def test_explicit_temperature_schedule_forwarded(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
        calls: list[dict] = []
        def fake(**kwargs):
            calls.append(kwargs)
            return ("ok", "", "gemini")
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            side_effect=fake,
        ):
            llm_repair_model_text_multi(
                planner_backend="gemini",
                original_text="x",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="",
                repair_actions=[],
                model_name="X",
                num_candidates=2,
                temperature_schedule=[0.1, 0.9],
                inter_call_delay_s=0.0,
                retry_backoff_s=0.0,
            )
        self.assertEqual([c["temperature_override"] for c in calls], [0.1, 0.9])

    def test_retry_recovers_on_transient_error(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
        # First call at temp=0.1 fails, retry succeeds. Second candidate succeeds first try.
        attempts: list[float] = []
        def fake(**kwargs):
            attempts.append(kwargs["temperature_override"])
            # Fail only on the FIRST occurrence of temp=0.1; succeed on retry.
            if kwargs["temperature_override"] == 0.1 and attempts.count(0.1) == 1:
                return (None, "rate_limit", "gemini")
            return ("recovered", "", "gemini")
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            side_effect=fake,
        ):
            results = llm_repair_model_text_multi(
                planner_backend="gemini",
                original_text="x",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="",
                repair_actions=[],
                model_name="X",
                num_candidates=2,
                inter_call_delay_s=0.0,
                retry_backoff_s=0.0,
                retry_on_error=True,
            )
        # 1 fail + 1 retry on candidate 0, 1 success on candidate 1 = 3 calls
        self.assertEqual(len(attempts), 3)
        self.assertEqual(attempts, [0.1, 0.1, 0.4])
        self.assertEqual(results[0]["patched_text"], "recovered")
        self.assertEqual(results[0]["llm_error"], "")
        self.assertEqual(results[1]["patched_text"], "recovered")

    def test_retry_disabled_does_not_retry(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
        attempts: list[float] = []
        def fake(**kwargs):
            attempts.append(kwargs["temperature_override"])
            return (None, "rate_limit", "gemini")
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            side_effect=fake,
        ):
            llm_repair_model_text_multi(
                planner_backend="gemini",
                original_text="x",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="",
                repair_actions=[],
                model_name="X",
                num_candidates=2,
                inter_call_delay_s=0.0,
                retry_backoff_s=0.0,
                retry_on_error=False,
            )
        self.assertEqual(len(attempts), 2)  # no retry

    def test_inter_call_delay_invoked_between_calls(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import llm_repair_model_text_multi
        def fake(**kwargs):
            return ("ok", "", "gemini")
        with patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.llm_repair_model_text",
            side_effect=fake,
        ), patch(
            "gateforge.agent_modelica_l2_plan_replan_engine_v1.time.sleep"
        ) as sleep_mock:
            llm_repair_model_text_multi(
                planner_backend="gemini",
                original_text="x",
                failure_type="underconstrained_system",
                expected_stage="check",
                error_excerpt="",
                repair_actions=[],
                model_name="X",
                num_candidates=3,
                inter_call_delay_s=0.5,
                retry_backoff_s=0.0,
            )
        # 3 calls -> 2 inter-call sleeps (skipped before first)
        self.assertEqual(sleep_mock.call_count, 2)
        for call in sleep_mock.call_args_list:
            self.assertEqual(call.args[0], 0.5)


if __name__ == "__main__":
    unittest.main()
