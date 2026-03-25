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
                "LLM_MODEL", "GATEFORGE_GEMINI_MODEL", "GEMINI_MODEL",
                "OPENAI_MODEL", "LLM_PROVIDER", "GATEFORGE_LIVE_PLANNER_BACKEND"]
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

    def test_defaults_to_gemini_when_only_gemini_key_present(self) -> None:
        prev = self._clear_provider_env()
        os.environ["GOOGLE_API_KEY"] = "google-key"
        try:
            with patch("gateforge.agent_modelica_l2_plan_replan_engine_v1.bootstrap_env_from_repo", return_value=0):
                provider, model, key = resolve_llm_provider("auto")
            self.assertEqual(provider, "gemini")
            self.assertEqual(key, "google-key")
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

    def test_unknown_family(self) -> None:
        self.assertEqual(planner_family_for_provider("mystery"), "unknown")

    def test_gemini_adapter(self) -> None:
        self.assertEqual(planner_adapter_for_provider("gemini"), "gateforge_gemini_planner_v1")

    def test_openai_adapter(self) -> None:
        self.assertEqual(planner_adapter_for_provider("openai"), "gateforge_openai_planner_v1")

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


if __name__ == "__main__":
    unittest.main()
