import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_live_executor_gemini_v1 import (
    _IN_MEMORY_LIVE_LEDGER,
    _apply_source_blind_multistep_branch_escape_search,
    _apply_source_blind_multistep_llm_plan,
    _apply_source_blind_multistep_exposure_repair,
    _apply_source_blind_multistep_llm_resolution,
    _apply_source_blind_multistep_local_search,
    _apply_source_blind_multistep_stage2_local_repair,
    _apply_behavioral_robustness_source_blind_local_repair,
    _apply_initialization_marker_repair,
    _behavioral_contract_deterministic_repair_enabled,
    _behavioral_robustness_source_mode,
    _normalize_behavioral_contract_text,
    _evaluate_behavioral_contract_from_model_text,
    _guard_robustness_patch,
    _apply_multi_round_layered_repair,
    _apply_parse_error_pre_repair,
    _apply_source_model_repair,
    _apply_wave2_1_marker_repair,
    _apply_wave2_2_marker_repair,
    _bootstrap_env_from_repo,
    _build_source_blind_multistep_llm_replan_context,
    _build_source_blind_multistep_replan_budget,
    _build_guided_search_execution_plan,
    _build_guided_search_observation_payload,
    _diagnostic_context_hints_from_model,
    _extract_om_success_flags,
    _extract_source_blind_multistep_markers,
    _extract_json_object,
    _llm_round_constraints,
    _llm_request_timeout_sec,
    _normalize_source_blind_multistep_llm_plan,
    _resolve_llm_plan_parameter_names,
    _looks_like_stage_1_focus,
    _live_budget_config,
    _normalize_terminal_errors,
    _openai_repair_model_text,
    _parse_env_assignment,
    _parse_repair_actions,
    _prepare_workspace_model_layout,
    _build_multistep_stage_context,
    _record_live_request_429,
    _resolve_llm_provider,
    _reserve_live_request,
    _run_omc_script_docker,
    _run_check_and_simulate,
    _select_initial_llm_plan_parameters,
    _temporary_workspace,
)


class AgentModelicaLiveExecutorGeminiV1Tests(unittest.TestCase):
    def test_diagnostic_context_hints_from_model_detects_underconstrained_probe_and_when_initial(self) -> None:
        hints = _diagnostic_context_hints_from_model(
            failure_type="underconstrained_system",
            expected_stage="check",
            model_text="model A\n  Real gateforge_underconstrained_probe_x;\nequation\n  when initial() then\n  end when;\nend A;\n",
        )
        self.assertIn("underconstrained_system", hints)
        self.assertIn("check", hints)
        self.assertIn("free_variable_probe", hints)
        self.assertIn("structural_underconstraint", hints)
        self.assertIn("when_initial_assert", hints)

    def test_temporary_workspace_supports_ignore_cleanup_errors(self) -> None:
        with _temporary_workspace(prefix="gf_live_exec_test_tmp_") as td:
            self.assertTrue(Path(td).exists())

    def test_temporary_workspace_cleanup_swallows_permission_error(self) -> None:
        with patch(
            "gateforge.agent_modelica_live_executor_gemini_v1.shutil.rmtree",
            side_effect=PermissionError("denied"),
        ):
            with _temporary_workspace(prefix="gf_live_exec_test_tmp_perm_") as td:
                self.assertTrue(Path(td).exists())

    def test_diagnostic_context_hints_include_wave2_1_markers(self) -> None:
        hints = _diagnostic_context_hints_from_model(
            failure_type="event_logic_error",
            expected_stage="simulate",
            model_text="model A\n  Real x;\nequation\n  der(x)=1; // gateforge_event_logic_error\n  assert(false, \"gateforge_semantic_drift_after_compile_pass\");\nend A;\n",
        )
        self.assertIn("event_logic_error", hints)
        self.assertIn("semantic_drift_after_compile_pass", hints)

    def test_diagnostic_context_hints_include_wave2_2_markers(self) -> None:
        hints = _diagnostic_context_hints_from_model(
            failure_type="mode_switch_guard_logic_error",
            expected_stage="simulate",
            model_text="model A\n  Real x;\nequation\n  der(x)=1; // gateforge_cross_component_parameter_coupling_error\n  assert(false, \"gateforge_mode_switch_guard_logic_error\");\nend A;\n",
        )
        self.assertIn("cross_component_parameter_coupling_error", hints)
        self.assertIn("mode_switch_guard_logic_error", hints)

    def test_run_check_and_simulate_loads_modelica_library(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_live_exec_modelica_") as td:
            workspace = Path(td)
            with patch(
                "gateforge.agent_modelica_live_executor_gemini_v1._run_omc_script_local",
                return_value=(0, "Check of A1 completed successfully.\nrecord SimulationResult\nresultFile = \"/tmp/a.mat\""),
            ) as mocked:
                _run_check_and_simulate(
                    workspace=workspace,
                    model_load_files=["A1.mo"],
                    model_name="A1",
                    timeout_sec=30,
                    backend="omc",
                    docker_image="unused",
                    stop_time=0.2,
                    intervals=20,
                )
                self.assertEqual(mocked.call_count, 1)
                script_text = str(mocked.call_args.kwargs.get("script_text") or mocked.call_args.args[0])
                self.assertIn("loadModel(Modelica);", script_text)
                self.assertIn('loadFile("A1.mo");', script_text)

    def test_run_check_and_simulate_bootstraps_modelica_in_docker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_live_exec_modelica_docker_") as td:
            workspace = Path(td)
            with patch(
                "gateforge.agent_modelica_live_executor_gemini_v1._run_omc_script_docker",
                return_value=(0, "Check of A1 completed successfully.\nrecord SimulationResult\nresultFile = \"/tmp/a.mat\""),
            ) as mocked:
                _run_check_and_simulate(
                    workspace=workspace,
                    model_load_files=["A1.mo"],
                    model_name="A1",
                    timeout_sec=30,
                    backend="openmodelica_docker",
                    docker_image="img",
                    stop_time=0.2,
                    intervals=20,
                )
                self.assertEqual(mocked.call_count, 1)
                script_text = str(mocked.call_args.kwargs.get("script_text") or mocked.call_args.args[0])
                self.assertIn("installPackage(Modelica);", script_text)
                self.assertIn("loadModel(Modelica);", script_text)
                self.assertIn('loadFile("A1.mo");', script_text)

    def test_prepare_workspace_model_layout_mirrors_external_library_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_live_exec_layout_") as td:
            root = Path(td)
            workspace = root / "workspace"
            library_root = root / "AixLib"
            package_file = library_root / "package.mo"
            model_file = library_root / "Systems" / "Examples" / "Demo.mo"
            package_file.parent.mkdir(parents=True, exist_ok=True)
            model_file.parent.mkdir(parents=True, exist_ok=True)
            package_file.write_text("within ;\npackage AixLib\nend AixLib;\n", encoding="utf-8")
            model_file.write_text("within AixLib.Systems.Examples;\nmodel Demo\nend Demo;\n", encoding="utf-8")
            workspace.mkdir(parents=True, exist_ok=True)

            layout = _prepare_workspace_model_layout(
                workspace=workspace,
                fallback_model_path=model_file,
                primary_model_name="Demo",
                source_library_path=str(library_root),
                source_package_name="AixLib",
                source_library_model_path=str(model_file),
                source_qualified_model_name="AixLib.Systems.Examples.Demo",
            )

            self.assertTrue(layout.uses_external_library)
            self.assertEqual(layout.model_identifier, "AixLib.Systems.Examples.Demo")
            self.assertEqual(layout.model_write_path, workspace / "AixLib" / "Systems" / "Examples" / "Demo.mo")
            self.assertTrue((workspace / "AixLib" / "package.mo").exists())
            self.assertIn("AixLib/package.mo", layout.model_load_files)
            self.assertIn("AixLib/Systems/Examples/Demo.mo", layout.model_load_files)

    def test_source_blind_multistep_local_search_generates_stage1_candidate(self) -> None:
        model_text = (
            "model SwitchA\n"
            "  parameter Real width=62;\n"
            "  parameter Real period=0.85;\n"
            "  parameter Real k=1.18;\n"
            "end SwitchA;\n"
        )
        patched, audit = _apply_source_blind_multistep_local_search(
            current_text=model_text,
            declared_failure_type="behavior_then_robustness",
            current_stage="stage_1",
            current_fail_bucket="",
            search_memory={},
        )
        self.assertTrue(audit.get("applied"))
        self.assertEqual(audit.get("search_kind"), "stage_1_unlock")
        self.assertEqual(audit.get("cluster_name"), "adaptive_combo")
        self.assertIn("width=40", str(audit.get("candidate_key") or ""))
        self.assertIn("period=0.5", patched)

    def test_extract_source_blind_multistep_markers_detects_llm_forcing(self) -> None:
        markers = _extract_source_blind_multistep_markers(
            "// gateforge_source_blind_multistep_realism_version:v4\n"
            "// gateforge_source_blind_multistep_llm_forcing:1\n"
            "// gateforge_source_blind_multistep_llm_profile:branch_unknown\n"
            "// gateforge_source_blind_multistep_llm_trigger:same_stage_2_branch_stall\n"
            "model SwitchB\nend SwitchB;\n"
        )
        self.assertEqual(markers.get("realism_version"), "v4")
        self.assertTrue(bool(markers.get("llm_forcing")))
        self.assertEqual(markers.get("llm_profile"), "branch_unknown")
        self.assertEqual(markers.get("llm_trigger"), "same_stage_2_branch_stall")

    def test_source_blind_multistep_llm_resolution_restores_switchb_behavior_bundle(self) -> None:
        model_text = (
            "// gateforge_source_blind_multistep_realism_version:v4\n"
            "// gateforge_source_blind_multistep_llm_forcing:1\n"
            "model SwitchB\n"
            "  parameter Real startTime=0.75;\n"
            "  parameter Real freqHz=1.6;\n"
            "  parameter Real k=0.82;\n"
            "end SwitchB;\n"
        )
        patched, audit = _apply_source_blind_multistep_llm_resolution(
            current_text=model_text,
            declared_failure_type="behavior_then_robustness",
            llm_reason="branch_diagnosis_unknown",
        )
        self.assertTrue(audit.get("applied"))
        self.assertIn("startTime=0.3", patched)
        self.assertIn("freqHz=1", patched)
        self.assertIn("k=0.5", patched)

    def test_normalize_source_blind_multistep_llm_plan_preserves_branch_and_parameters(self) -> None:
        plan = _normalize_source_blind_multistep_llm_plan(
            payload={
                "diagnosed_stage": "stage_2",
                "diagnosed_branch": "neighbor_overfit_trap",
                "preferred_branch": "behavior_timing_branch",
                "repair_goal": "escape trap and restore timing behavior",
                "candidate_parameters": ["startTime", "height"],
                "candidate_value_directions": ["startTime:decrease", "height:normalize"],
                "why_not_other_branch": "nominal fit is overfitting neighbors",
                "stop_condition": "stop when preferred branch is restored",
            },
            stage_context={"current_stage": "stage_2", "stage_2_branch": "neighbor_overfit_trap", "preferred_stage_2_branch": "behavior_timing_branch"},
            llm_reason="trap_escape_no_progress",
        )
        self.assertEqual(plan.get("diagnosed_stage"), "stage_2")
        self.assertEqual(plan.get("diagnosed_branch"), "neighbor_overfit_trap")
        self.assertEqual(plan.get("preferred_branch"), "behavior_timing_branch")
        self.assertEqual(plan.get("candidate_parameters"), ["startTime", "height"])

    def test_source_blind_multistep_llm_plan_executes_requested_parameter_subset(self) -> None:
        model_text = (
            "model PlantB\n"
            "  parameter Real height=1.2;\n"
            "  parameter Real duration=1.1;\n"
            "  parameter Real startTime=0.8;\n"
            "end PlantB;\n"
        )
        patched, audit = _apply_source_blind_multistep_llm_plan(
            current_text=model_text,
            declared_failure_type="stability_then_behavior",
            llm_plan={
                "candidate_parameters": ["height", "duration"],
                "candidate_value_directions": ["height:normalize", "duration:decrease"],
            },
            llm_reason="same_stage_2_branch_stall",
        )
        self.assertTrue(audit.get("applied"))
        self.assertIn("height=1", patched)
        self.assertIn("duration=0.5", patched)
        self.assertNotIn("startTime=0.2", patched)

    def test_source_blind_multistep_llm_plan_falls_back_from_satisfied_subset(self) -> None:
        model_text = (
            "model SwitchB\n"
            "  parameter Real startTime=0.3;\n"
            "  parameter Real freqHz=1.6;\n"
            "  parameter Real k=0.82;\n"
            "end SwitchB;\n"
        )
        patched, audit = _apply_source_blind_multistep_llm_plan(
            current_text=model_text,
            declared_failure_type="behavior_then_robustness",
            llm_plan={
                "candidate_parameters": ["startTime"],
                "candidate_value_directions": ["startTime:keep"],
            },
            llm_reason="same_stage_2_branch_stall_after_replan",
            parameter_names_override=["startTime"],
        )
        self.assertTrue(audit.get("applied"))
        self.assertIn("freqHz=1", patched)
        self.assertIn("k=0.5", patched)

    def test_build_source_blind_multistep_llm_replan_context_detects_same_branch_stall(self) -> None:
        context = _build_source_blind_multistep_llm_replan_context(
            current_text=(
                "// gateforge_source_blind_multistep_realism_version:v4\n"
                "// gateforge_source_blind_multistep_llm_forcing:1\n"
                "model SwitchB\n"
                "  parameter Real k=0.82;\n"
                "end SwitchB;\n"
            ),
            stage_context={
                "current_stage": "stage_2",
                "stage_2_branch": "neighbor_robustness_branch",
                "preferred_stage_2_branch": "behavior_timing_branch",
                "branch_mode": "preferred",
                "trap_branch": False,
            },
            current_round=2,
            memory={
                "llm_plan_followed": True,
                "llm_replan_used": False,
                "last_llm_plan_branch": "neighbor_robustness_branch",
                "last_llm_plan_fail_bucket": "single_case_only",
                "last_llm_plan_pass_count": 1,
            },
            contract_fail_bucket="single_case_only",
            scenario_results=[
                {"scenario_id": "nominal", "pass": True},
                {"scenario_id": "neighbor_a", "pass": False},
                {"scenario_id": "neighbor_b", "pass": False},
            ],
        )
        self.assertTrue(bool(context.get("should_force_replan")))
        self.assertEqual(str(context.get("previous_plan_failed_signal") or ""), "same_stage_2_branch_stall_after_first_plan")
        self.assertEqual(str(context.get("previous_branch") or ""), "neighbor_robustness_branch")

    def test_build_source_blind_multistep_replan_budget_prefers_branch_switch_for_trap(self) -> None:
        budget = _build_source_blind_multistep_replan_budget(
            stage_context={
                "trap_branch": True,
                "stage_2_branch": "nominal_overfit_trap",
                "preferred_stage_2_branch": "behavior_timing_branch",
            },
            replan_context={
                "previous_plan_failed_signal": "trap_branch_no_escape_progress",
                "current_branch": "nominal_overfit_trap",
                "preferred_branch": "behavior_timing_branch",
            },
            current_round=2,
            max_rounds=3,
            memory={},
        )
        self.assertTrue(bool(budget.get("replan_switch_branch")))
        self.assertFalse(bool(budget.get("replan_continue_current_branch")))
        self.assertGreaterEqual(int(budget.get("replan_budget_for_branch_escape") or 0), 1)
        self.assertIn("switch away", str(budget.get("branch_choice_reason") or ""))

    def test_build_guided_search_execution_plan_enforces_resolution_budget(self) -> None:
        plan = _build_guided_search_execution_plan(
            llm_plan={
                "replan_budget_for_branch_diagnosis": 1,
                "replan_budget_for_branch_escape": 1,
                "replan_budget_for_resolution": 1,
                "guided_search_bucket_sequence": ["branch_diagnosis", "branch_escape", "resolution"],
                "switch_to_branch": "neighbor_robustness_branch",
                "replan_switch_branch": True,
            },
            stage_context={
                "stage_2_branch": "nominal_overfit_trap",
                "preferred_stage_2_branch": "neighbor_robustness_branch",
                "trap_branch": True,
            },
            requested_parameters=["offset", "k", "startTime"],
            ordered_targets=["offset", "k", "startTime"],
            previous_branch="nominal_overfit_trap",
        )
        self.assertEqual(plan.get("execution_parameters"), ["offset"])
        self.assertEqual(int(plan.get("candidate_suppressed_by_budget") or 0), 2)
        self.assertEqual(plan.get("budget_bucket_exhausted"), ["branch_diagnosis", "branch_escape", "resolution"])
        self.assertEqual((plan.get("budget_bucket_consumed") or {}).get("resolution"), 1)

    def test_build_guided_search_observation_payload_marks_no_progress_buckets(self) -> None:
        observation = _build_guided_search_observation_payload(
            memory={
                "last_guided_search_bucket_sequence": ["branch_diagnosis", "branch_escape", "resolution"],
                "last_budget_spent_by_bucket": {"branch_diagnosis": 1, "branch_escape": 1, "resolution": 1},
                "last_candidate_attempt_count_by_bucket": {"branch_diagnosis": 1, "branch_escape": 1, "resolution": 1},
                "last_llm_plan_pass_count": 1,
                "replan_abandoned_branches": ["nominal_overfit_trap"],
                "replan_same_branch_stall_count": 1,
                "last_candidate_suppressed_by_budget": 2,
                "last_resolution_skipped_due_to_budget": False,
                "last_branch_escape_skipped_due_to_budget": False,
                "last_branch_frozen_by_budget": ["nominal_overfit_trap"],
            },
            stage_context={
                "current_stage": "stage_2",
                "stage_2_branch": "nominal_overfit_trap",
                "preferred_stage_2_branch": "neighbor_robustness_branch",
                "branch_mode": "trap",
            },
            contract_fail_bucket="single_case_only",
            scenario_results=[
                {"scenario_id": "nominal", "pass": True},
                {"scenario_id": "neighbor_a", "pass": False},
                {"scenario_id": "neighbor_b", "pass": False},
            ],
        )
        self.assertEqual((observation.get("best_progress_by_bucket") or {}).get("resolution"), 0)
        self.assertIn("branch_escape", observation.get("no_progress_buckets") or [])
        self.assertEqual(observation.get("abandoned_branches"), ["nominal_overfit_trap"])
        self.assertEqual(observation.get("branch_frozen_by_budget"), ["nominal_overfit_trap"])

    def test_select_initial_llm_plan_parameters_prefers_first_available_parameter(self) -> None:
        selected = _select_initial_llm_plan_parameters(
            llm_plan={"candidate_parameters": ["offset", "k", "startTime"]},
            available_targets={"k": 0.5, "startTime": 0.3},
        )
        self.assertEqual(selected, ["k"])

    def test_select_initial_llm_plan_parameters_prefers_gate_pair_for_behavior_then_robustness(self) -> None:
        selected = _select_initial_llm_plan_parameters(
            llm_plan={"candidate_parameters": ["startTime", "freqHz", "k"]},
            available_targets={"startTime": 0.3, "freqHz": 1.0, "k": 0.5},
        )
        self.assertEqual(selected, ["startTime", "freqHz"])

    def test_resolve_llm_plan_parameter_names_normalizes_component_qualified_names(self) -> None:
        resolved = _resolve_llm_plan_parameter_names(
            requested_names=["step1.startTime", "sine1.f", "ref1.k"],
            available_targets={"startTime": 0.3, "freqHz": 1.0, "k": 0.5},
        )
        self.assertEqual(resolved, ["startTime", "freqHz", "k"])

    def test_live_ledger_uses_in_memory_fallback_without_path(self) -> None:
        _IN_MEMORY_LIVE_LEDGER.clear()
        cfg = _live_budget_config()
        self.assertEqual(str(cfg.get("ledger_path") or ""), "")
        before = _reserve_live_request(cfg)[1]
        self.assertEqual(int(before.get("request_count") or 0), 1)
        after = _record_live_request_429(cfg)[1]
        self.assertEqual(int(after.get("request_count") or 0), 1)
        self.assertEqual(int(after.get("rate_limit_429_count") or 0), 1)
        loaded = _reserve_live_request(cfg)[1]
        self.assertEqual(int(loaded.get("request_count") or 0), 2)

    def test_source_blind_multistep_local_search_prefers_plantb_stage1_unlock_bundle(self) -> None:
        model_text = (
            "model PlantB\n"
            "  parameter Real height=1.2;\n"
            "  parameter Real duration=1.1;\n"
            "  parameter Real startTime=0.8;\n"
            "end PlantB;\n"
        )
        patched, audit = _apply_source_blind_multistep_local_search(
            current_text=model_text,
            declared_failure_type="stability_then_behavior",
            current_stage="stage_1",
            current_fail_bucket="",
            search_memory={},
        )
        self.assertTrue(audit.get("applied"))
        self.assertEqual(audit.get("cluster_name"), "adaptive_combo")
        self.assertIn("height=1", patched)
        self.assertIn("duration=0.5", patched)
        self.assertEqual(audit.get("candidate_origin"), "adaptive_search")
        self.assertGreaterEqual(int(audit.get("candidate_pool_size") or 0), 1)

    def test_source_blind_multistep_local_search_generates_stage2_candidate(self) -> None:
        model_text = (
            "model HybridB\n"
            "  parameter Real startTime=0.6;\n"
            "  parameter Real k=0.6;\n"
            "  parameter Real width=0.75;\n"
            "  parameter Real T=0.5;\n"
            "end HybridB;\n"
        )
        patched, audit = _apply_source_blind_multistep_local_search(
            current_text=model_text,
            declared_failure_type="switch_then_recovery",
            current_stage="stage_2",
            current_fail_bucket="post_switch_recovery_miss",
            search_memory={},
        )
        self.assertTrue(audit.get("applied"))
        self.assertEqual(audit.get("search_kind"), "stage_2_resolution")
        self.assertIn("width=", str(audit.get("candidate_key") or ""))
        self.assertNotEqual(patched, model_text)

    def test_source_blind_multistep_local_search_prefers_hybridb_stage2_full_candidate(self) -> None:
        model_text = (
            "model HybridB\n"
            "  parameter Real width=0.75;\n"
            "  parameter Real T=0.5;\n"
            "  parameter Real startTime=0.2;\n"
            "end HybridB;\n"
        )
        patched, audit = _apply_source_blind_multistep_local_search(
            current_text=model_text,
            declared_failure_type="switch_then_recovery",
            current_stage="stage_2",
            current_fail_bucket="post_switch_recovery_miss",
            search_memory={},
        )
        self.assertTrue(audit.get("applied"))
        self.assertEqual(audit.get("cluster_name"), "adaptive_combo")
        self.assertIn("width=0.4", patched)
        self.assertIn("T=0.2", patched)
        self.assertEqual(audit.get("candidate_origin"), "adaptive_search")
        self.assertEqual(audit.get("search_direction"), "width+T")

    def test_source_blind_multistep_local_search_skips_tried_candidate(self) -> None:
        model_text = (
            "model HybridB\n"
            "  parameter Real width=0.75;\n"
            "  parameter Real T=0.5;\n"
            "end HybridB;\n"
        )
        _, first_audit = _apply_source_blind_multistep_local_search(
            current_text=model_text,
            declared_failure_type="switch_then_recovery",
            current_stage="stage_2",
            current_fail_bucket="post_switch_recovery_miss",
            search_memory={},
        )
        patched, second_audit = _apply_source_blind_multistep_local_search(
            current_text=model_text,
            declared_failure_type="switch_then_recovery",
            current_stage="stage_2",
            current_fail_bucket="post_switch_recovery_miss",
            search_memory={"tried_candidate_values": [str(first_audit.get("candidate_key") or "")]},
        )
        self.assertTrue(second_audit.get("applied"))
        self.assertNotEqual(second_audit.get("candidate_key"), first_audit.get("candidate_key"))
        self.assertNotEqual(patched, model_text)

    def test_source_blind_multistep_branch_escape_search_restores_hybridb_recovery_branch(self) -> None:
        model_text = (
            "model HybridB\n"
            "  parameter Real startTime=0.6;\n"
            "  parameter Real k=0.6;\n"
            "  parameter Real width=0.75;\n"
            "  parameter Real T=0.5;\n"
            "end HybridB;\n"
        )
        patched, audit = _apply_source_blind_multistep_branch_escape_search(
            current_text=model_text,
            declared_failure_type="switch_then_recovery",
            current_branch="recovery_overfit_trap",
            preferred_branch="post_switch_recovery_branch",
            search_memory={},
        )
        self.assertTrue(audit.get("applied"))
        self.assertEqual(audit.get("search_kind"), "branch_escape")
        self.assertEqual(audit.get("cluster_name"), "escape_recovery_overfit_full")
        self.assertEqual(audit.get("candidate_origin"), "branch_escape_template")
        self.assertEqual(audit.get("search_direction"), "startTime+k+width+T")
        self.assertIn("startTime=0.1", patched)
        self.assertIn("k=1", patched)
        self.assertIn("width=0.4", patched)
        self.assertIn("T=0.2", patched)

    def test_extract_om_success_flags_treats_structural_mismatch_as_check_failure(self) -> None:
        check_ok, simulate_ok = _extract_om_success_flags(
            'Check of SmallRDividerV0 completed successfully.\nClass SmallRDividerV0 has 32 equation(s) and 33 variable(s).\n'
        )
        self.assertFalse(check_ok)
        self.assertFalse(simulate_ok)

    def test_live_budget_reserve_stops_when_request_cap_is_reached(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_live_budget_") as td:
            ledger = Path(td) / "ledger.json"
            prev = {
                "GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH": os.environ.get("GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH"),
                "GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN": os.environ.get("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN"),
            }
            os.environ["GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH"] = str(ledger)
            os.environ["GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN"] = "1"
            try:
                cfg = _live_budget_config()
                allowed, _ = _reserve_live_request(cfg)
                self.assertTrue(allowed)
                allowed, state = _reserve_live_request(cfg)
                self.assertFalse(allowed)
                self.assertTrue(bool(state.get("budget_stop_triggered")))
                self.assertEqual(str(state.get("last_stop_reason") or ""), "live_request_budget_exceeded")
            finally:
                for key, value in prev.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_live_budget_429_stop_sets_rate_limited(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_live_budget_429_") as td:
            ledger = Path(td) / "ledger.json"
            prev = {
                "GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH": os.environ.get("GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH"),
                "GATEFORGE_AGENT_LIVE_MAX_CONSECUTIVE_429": os.environ.get("GATEFORGE_AGENT_LIVE_MAX_CONSECUTIVE_429"),
                "GATEFORGE_AGENT_LIVE_BACKOFF_BASE_SEC": os.environ.get("GATEFORGE_AGENT_LIVE_BACKOFF_BASE_SEC"),
                "GATEFORGE_AGENT_LIVE_BACKOFF_MAX_SEC": os.environ.get("GATEFORGE_AGENT_LIVE_BACKOFF_MAX_SEC"),
            }
            os.environ["GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH"] = str(ledger)
            os.environ["GATEFORGE_AGENT_LIVE_MAX_CONSECUTIVE_429"] = "2"
            os.environ["GATEFORGE_AGENT_LIVE_BACKOFF_BASE_SEC"] = "0"
            os.environ["GATEFORGE_AGENT_LIVE_BACKOFF_MAX_SEC"] = "0"
            try:
                cfg = _live_budget_config()
                stop_reason, _ = _record_live_request_429(cfg)
                self.assertEqual(stop_reason, "")
                stop_reason, state = _record_live_request_429(cfg)
                self.assertEqual(stop_reason, "rate_limited")
                self.assertEqual(int(state.get("rate_limit_429_count") or 0), 2)
                self.assertTrue(bool(state.get("budget_stop_triggered")))
            finally:
                for key, value in prev.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_run_omc_script_docker_mounts_cache_dir(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_live_exec_docker_cache_") as td:
            workspace = Path(td)
            cache_dir = workspace / "cache"
            prev = os.environ.get("GATEFORGE_OM_DOCKER_LIBRARY_CACHE")
            os.environ["GATEFORGE_OM_DOCKER_LIBRARY_CACHE"] = str(cache_dir)
            try:
                with patch(
                    "gateforge.agent_modelica_live_executor_gemini_v1._run_cmd",
                    return_value=(0, "ok"),
                ) as mocked:
                    _run_omc_script_docker(
                        script_text="getErrorString();\n",
                        timeout_sec=30,
                        cwd=str(workspace),
                        image="img",
                    )
                    self.assertEqual(mocked.call_count, 1)
                    cmd = mocked.call_args.args[0]
                    self.assertIn(f"{str(cache_dir.resolve())}:/tmp/.openmodelica/libraries", cmd)
                    self.assertIn("--user", cmd)
                    self.assertIn("-e", cmd)
                    self.assertIn("HOME=/tmp", cmd)
            finally:
                if prev is None:
                    os.environ.pop("GATEFORGE_OM_DOCKER_LIBRARY_CACHE", None)
                else:
                    os.environ["GATEFORGE_OM_DOCKER_LIBRARY_CACHE"] = prev

    def test_normalize_terminal_errors_clears_errors_for_pass(self) -> None:
        err, comp, sim = _normalize_terminal_errors("PASS", "x", "y", "z")
        self.assertEqual((err, comp, sim), ("", "", ""))

    def test_normalize_terminal_errors_keeps_errors_for_failed(self) -> None:
        err, comp, sim = _normalize_terminal_errors("FAILED", "x", "y", "z")
        self.assertEqual((err, comp, sim), ("x", "y", "z"))

    def test_behavioral_contract_eval_fails_when_marker_mutation_remains(self) -> None:
        source = "model A\n  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);\nend A;\n"
        mutated = "model A\n  // gateforge_behavioral_contract_violation:steady_state_target_violation\n  Modelica.Blocks.Sources.Step step1(height=0.82, startTime=0.1);\nend A;\n"
        payload = _evaluate_behavioral_contract_from_model_text(
            current_text=mutated,
            source_model_text=source,
            failure_type="steady_state_target_violation",
        )
        self.assertFalse(bool(payload.get("pass")))
        self.assertEqual(payload.get("contract_fail_bucket"), "steady_state_miss")

    def test_guard_robustness_patch_rejects_invented_switch_threshold(self) -> None:
        original = "model SwitchA\n  Modelica.Blocks.Logical.Switch sw1;\nend SwitchA;\n"
        patched = "model SwitchA\n  Modelica.Blocks.Logical.Switch sw1(threshold=0.2);\nend SwitchA;\n"
        guarded, audit = _guard_robustness_patch(
            original_text=original,
            patched_text=patched,
            failure_type="initial_condition_robustness_violation",
        )
        self.assertIsNone(guarded)
        self.assertEqual(audit.get("reason"), "invented_switch_threshold_parameter")

    def test_guard_robustness_patch_allows_existing_parameter_adjustment(self) -> None:
        original = "model A\n  Modelica.Blocks.Sources.BooleanPulse pulse1(width=40, period=0.5);\nend A;\n"
        patched = "model A\n  Modelica.Blocks.Sources.BooleanPulse pulse1(width=18, period=0.28);\nend A;\n"
        guarded, audit = _guard_robustness_patch(
            original_text=original,
            patched_text=patched,
            failure_type="initial_condition_robustness_violation",
        )
        self.assertEqual(guarded, patched)
        self.assertTrue(bool(audit.get("accepted")))

    def test_guard_robustness_patch_rejects_structure_drift(self) -> None:
        original = (
            "model A\n"
            "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=40, period=0.5);\n"
            "  Modelica.Blocks.Logical.Switch sw1;\n"
            "equation\n"
            "  connect(pulse1.y, sw1.u2);\n"
            "end A;\n"
        )
        patched = (
            "model A\n"
            "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=18, period=0.28);\n"
            "  Modelica.Blocks.Logical.Switch sw1;\n"
            "equation\n"
            "  connect(pulse1.y, sw1.u1);\n"
            "end A;\n"
        )
        guarded, audit = _guard_robustness_patch(
            original_text=original,
            patched_text=patched,
            failure_type="scenario_switch_robustness_violation",
        )
        self.assertIsNone(guarded)
        self.assertEqual(audit.get("reason"), "robustness_structure_drift_detected")

    def test_behavioral_contract_eval_passes_when_source_restored(self) -> None:
        source = "model A\n  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);\nend A;\n"
        payload = _evaluate_behavioral_contract_from_model_text(
            current_text=source,
            source_model_text=source,
            failure_type="steady_state_target_violation",
        )
        self.assertTrue(bool(payload.get("pass")))

    def test_behavioral_contract_source_restore_gate_uses_env_flag(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_DETERMINISTIC_REPAIR")
        os.environ["GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_DETERMINISTIC_REPAIR"] = "1"
        try:
            self.assertTrue(_behavioral_contract_deterministic_repair_enabled())
            patched, audit = _apply_source_model_repair(
                current_text="model A\n// gateforge_behavioral_contract_violation:steady_state_target_violation\nend A;\n",
                source_model_text="model A\nend A;\n",
                declared_failure_type="steady_state_target_violation",
                observed_failure_type="semantic_regression",
            )
            self.assertTrue(bool(audit.get("applied")))
            self.assertEqual(patched, "model A\nend A;\n")
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_DETERMINISTIC_REPAIR"] = prev

    def test_behavioral_robustness_source_mode_defaults_to_source_aware(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE")
        try:
            os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE", None)
            self.assertEqual(_behavioral_robustness_source_mode(), "source_aware")
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = prev

    def test_behavioral_robustness_source_blind_disables_source_repair(self) -> None:
        prev_det = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR")
        prev_mode = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE")
        os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR"] = "1"
        os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = "source_blind"
        try:
            patched, audit = _apply_source_model_repair(
                current_text="model A\n  parameter Real k=0.8;\nend A;\n",
                source_model_text="model A\n  parameter Real k=1.0;\nend A;\n",
                declared_failure_type="param_perturbation_robustness_violation",
                observed_failure_type="single_case_only",
            )
            self.assertFalse(bool(audit.get("applied")))
            self.assertEqual(str(audit.get("reason") or ""), "behavioral_robustness_source_blind_disables_source_repair")
            self.assertIn("k=0.8", patched)
        finally:
            if prev_det is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR"] = prev_det
            if prev_mode is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = prev_mode

    def test_behavioral_robustness_source_blind_local_repair_restores_switcha_initial_cluster(self) -> None:
        prev_det = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR")
        prev_mode = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE")
        os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR"] = "1"
        os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = "source_blind"
        try:
            current = (
                "model SwitchA\n"
                "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=18, period=0.28);\n"
                "  Modelica.Blocks.Sources.Constant c1(k=1);\n"
                "  Modelica.Blocks.Sources.Constant c0(k=0);\n"
                "  Modelica.Blocks.Logical.Switch sw1;\n"
                "equation\n"
                "  connect(c1.y, sw1.u1);\n"
                "  connect(pulse1.y, sw1.u2);\n"
                "  connect(c0.y, sw1.u3);\n"
                "end SwitchA;\n"
            )
            patched, audit = _apply_behavioral_robustness_source_blind_local_repair(
                current_text=current,
                declared_failure_type="initial_condition_robustness_violation",
                current_round=1,
            )
            self.assertTrue(bool(audit.get("applied")))
            self.assertIn("width=40", patched)
            self.assertIn("period=0.5", patched)
        finally:
            if prev_det is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR"] = prev_det
            if prev_mode is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = prev_mode

    def test_behavioral_robustness_source_blind_local_repair_restores_hybrida_scenario_cluster(self) -> None:
        prev_det = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR")
        prev_mode = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE")
        os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR"] = "1"
        os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = "source_blind"
        try:
            current = (
                "model HybridA\n"
                "  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.6);\n"
                "  Modelica.Blocks.Continuous.Integrator int1(k=0.6);\n"
                "equation\n"
                "  connect(step1.y, int1.u);\n"
                "end HybridA;\n"
            )
            patched, audit = _apply_behavioral_robustness_source_blind_local_repair(
                current_text=current,
                declared_failure_type="scenario_switch_robustness_violation",
                current_round=1,
            )
            self.assertTrue(bool(audit.get("applied")))
            self.assertIn("startTime=0.2", patched)
            self.assertIn("k=1", patched)
            self.assertNotIn("connect(", str(audit))
        finally:
            if prev_det is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR"] = prev_det
            if prev_mode is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = prev_mode

    def test_behavioral_robustness_source_blind_local_repair_restores_hybridb_scenario_cluster(self) -> None:
        prev_det = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR")
        prev_mode = os.environ.get("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE")
        os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR"] = "1"
        os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = "source_blind"
        try:
            current = (
                "model HybridB\n"
                "  parameter Real amplitude=1;\n"
                "  parameter Real width=0.4;\n"
                "  parameter Real period=1.0;\n"
                "  parameter Real startTime=0.6;\n"
                "  Modelica.Blocks.Sources.RealExpression trap1(y=if time < startTime then 0 else if time < startTime + width then amplitude else 0);\n"
                "  Modelica.Blocks.Continuous.FirstOrder first1(T=0.2, k=0.6);\n"
                "equation\n"
                "  connect(trap1.y, first1.u);\n"
                "end HybridB;\n"
            )
            patched, audit = _apply_behavioral_robustness_source_blind_local_repair(
                current_text=current,
                declared_failure_type="scenario_switch_robustness_violation",
                current_round=1,
            )
            self.assertTrue(bool(audit.get("applied")))
            self.assertIn("startTime=0.1", patched)
            self.assertIn("k=1", patched)
        finally:
            if prev_det is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_DETERMINISTIC_REPAIR"] = prev_det
            if prev_mode is None:
                os.environ.pop("GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE", None)
            else:
                os.environ["GATEFORGE_AGENT_BEHAVIORAL_ROBUSTNESS_SOURCE_MODE"] = prev_mode

    def test_normalize_behavioral_contract_text_ignores_robustness_markers(self) -> None:
        source = (
            "model PlantA\n"
            "  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);\n"
            "end PlantA;\n"
        )
        candidate = (
            "model PlantA\n"
            "  // gateforge_behavioral_robustness_violation:param_perturbation_robustness_violation\n"
            "  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);\n"
            "end PlantA;\n"
        )
        self.assertEqual(
            _normalize_behavioral_contract_text(candidate),
            _normalize_behavioral_contract_text(source),
        )

    def test_source_blind_multistep_contract_eval_exposes_second_stage(self) -> None:
        source = "model A\n  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);\n  Real k=1;\nend A;\n"
        stage1 = "model A\n  Modelica.Blocks.Sources.Step step1(height=1.12, startTime=0.45);\n  Real k=1.18;\nend A;\n"
        stage2 = "model A\n  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.45);\n  Real k=1;\nend A;\n"
        eval1 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage1,
            source_model_text=source,
            failure_type="stability_then_behavior",
        )
        eval2 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage2,
            source_model_text=source,
            failure_type="stability_then_behavior",
        )
        self.assertFalse(bool(eval1.get("pass")))
        self.assertEqual(str(eval1.get("contract_fail_bucket") or ""), "stability_margin_miss")
        self.assertEqual(str(eval1.get("multi_step_stage") or ""), "stage_1")
        self.assertFalse(bool(eval1.get("multi_step_stage_2_unlocked")))
        self.assertFalse(bool(eval2.get("pass")))
        self.assertEqual(str(eval2.get("contract_fail_bucket") or ""), "single_case_only")
        self.assertEqual(str(eval2.get("multi_step_stage") or ""), "stage_2")
        self.assertTrue(bool(eval2.get("multi_step_stage_2_unlocked")))
        self.assertEqual(str(eval2.get("stage_2_branch") or ""), "neighbor_overfit_trap")
        self.assertTrue(bool(eval2.get("trap_branch")))

    def test_source_blind_multistep_contract_eval_handles_switchb_two_stage_path(self) -> None:
        source = (
            "model SwitchB\n"
            "  parameter Real startTime=0.3;\n"
            "  Modelica.Blocks.Sources.BooleanExpression step1(y=time >= startTime);\n"
            "  Modelica.Blocks.Sources.Sine sine1(freqHz=1);\n"
            "  Modelica.Blocks.Sources.Constant ref1(k=0.5);\n"
            "end SwitchB;\n"
        )
        stage1 = (
            "model SwitchB\n"
            "  parameter Real startTime=0.75;\n"
            "  Modelica.Blocks.Sources.BooleanExpression step1(y=time >= startTime);\n"
            "  Modelica.Blocks.Sources.Sine sine1(freqHz=1.6);\n"
            "  Modelica.Blocks.Sources.Constant ref1(k=0.82);\n"
            "end SwitchB;\n"
        )
        stage2 = (
            "model SwitchB\n"
            "  parameter Real startTime=0.3;\n"
            "  Modelica.Blocks.Sources.BooleanExpression step1(y=time >= startTime);\n"
            "  Modelica.Blocks.Sources.Sine sine1(freqHz=1);\n"
            "  Modelica.Blocks.Sources.Constant ref1(k=0.82);\n"
            "end SwitchB;\n"
        )
        eval1 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage1,
            source_model_text=source,
            failure_type="behavior_then_robustness",
        )
        eval2 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage2,
            source_model_text=source,
            failure_type="behavior_then_robustness",
        )
        self.assertEqual(str(eval1.get("contract_fail_bucket") or ""), "behavior_contract_miss")
        self.assertEqual(str(eval2.get("contract_fail_bucket") or ""), "behavior_contract_miss")
        self.assertEqual(str(eval1.get("multi_step_stage") or ""), "stage_1")
        self.assertEqual(str(eval2.get("multi_step_stage") or ""), "stage_2")
        self.assertTrue(bool(eval2.get("multi_step_transition_seen")))
        self.assertEqual(str(eval2.get("stage_2_branch") or ""), "nominal_overfit_trap")
        self.assertTrue(bool(eval2.get("trap_branch")))

    def test_source_blind_multistep_contract_eval_handles_hybridb_two_stage_path(self) -> None:
        source = (
            "model HybridB\n"
            "  parameter Real amplitude=1;\n"
            "  parameter Real width=0.4;\n"
            "  parameter Real period=1.0;\n"
            "  parameter Real startTime=0.1;\n"
            "  Modelica.Blocks.Sources.RealExpression trap1(y=if time < startTime then 0 else if time < startTime + width then amplitude else 0);\n"
            "  Modelica.Blocks.Continuous.FirstOrder first1(T=0.2, k=1);\n"
            "end HybridB;\n"
        )
        stage1 = (
            "model HybridB\n"
            "  parameter Real amplitude=1;\n"
            "  parameter Real width=0.75;\n"
            "  parameter Real period=1.0;\n"
            "  parameter Real startTime=0.6;\n"
            "  Modelica.Blocks.Sources.RealExpression trap1(y=if time < startTime then 0 else if time < startTime + width then amplitude else 0);\n"
            "  Modelica.Blocks.Continuous.FirstOrder first1(T=0.5, k=0.6);\n"
            "end HybridB;\n"
        )
        stage2 = (
            "model HybridB\n"
            "  parameter Real amplitude=1;\n"
            "  parameter Real width=0.75;\n"
            "  parameter Real period=1.0;\n"
            "  parameter Real startTime=0.1;\n"
            "  Modelica.Blocks.Sources.RealExpression trap1(y=if time < startTime then 0 else if time < startTime + width then amplitude else 0);\n"
            "  Modelica.Blocks.Continuous.FirstOrder first1(T=0.5, k=1);\n"
            "end HybridB;\n"
        )
        eval1 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage1,
            source_model_text=source,
            failure_type="switch_then_recovery",
        )
        eval2 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage2,
            source_model_text=source,
            failure_type="switch_then_recovery",
        )
        self.assertEqual(str(eval1.get("contract_fail_bucket") or ""), "scenario_switch_miss")
        self.assertEqual(str(eval2.get("contract_fail_bucket") or ""), "single_case_only")
        self.assertEqual(str(eval1.get("multi_step_stage") or ""), "stage_1")
        self.assertEqual(str(eval2.get("multi_step_stage") or ""), "stage_2")
        self.assertEqual(str(eval2.get("multi_step_transition_reason") or ""), "switch_segment_restored_recovery_gate_exposed")
        self.assertEqual(str(eval2.get("stage_2_branch") or ""), "recovery_overfit_trap")
        self.assertTrue(bool(eval2.get("trap_branch")))

    def test_source_blind_multistep_contract_eval_handles_switcha_stability_two_stage_path(self) -> None:
        source = (
            "model SwitchA\n"
            "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=40, period=0.5);\n"
            "  Modelica.Blocks.Sources.Constant c1(k=1);\n"
            "end SwitchA;\n"
        )
        stage1 = (
            "model SwitchA\n"
            "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=62, period=0.85);\n"
            "  Modelica.Blocks.Sources.Constant c1(k=1.18);\n"
            "end SwitchA;\n"
        )
        stage2 = (
            "model SwitchA\n"
            "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=62, period=0.85);\n"
            "  Modelica.Blocks.Sources.Constant c1(k=1);\n"
            "end SwitchA;\n"
        )
        eval1 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage1,
            source_model_text=source,
            failure_type="stability_then_behavior",
        )
        eval2 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage2,
            source_model_text=source,
            failure_type="stability_then_behavior",
        )
        self.assertEqual(str(eval1.get("contract_fail_bucket") or ""), "stability_margin_miss")
        self.assertEqual(str(eval2.get("contract_fail_bucket") or ""), "behavior_contract_miss")
        self.assertEqual(str(eval1.get("multi_step_stage") or ""), "stage_1")
        self.assertEqual(str(eval2.get("multi_step_stage") or ""), "stage_2")
        self.assertEqual(str(eval2.get("stage_2_branch") or ""), "behavior_timing_branch")
        self.assertFalse(bool(eval2.get("trap_branch")))

    def test_source_blind_multistep_contract_eval_handles_plantb_switch_recovery_two_stage_path(self) -> None:
        source = (
            "model PlantB\n"
            "  Modelica.Blocks.Sources.Ramp ramp1(height=1, duration=0.5, startTime=0.2);\n"
            "end PlantB;\n"
        )
        stage1 = (
            "model PlantB\n"
            "  Modelica.Blocks.Sources.Ramp ramp1(height=1, duration=1.1, startTime=0.6);\n"
            "end PlantB;\n"
        )
        stage2 = (
            "model PlantB\n"
            "  Modelica.Blocks.Sources.Ramp ramp1(height=1, duration=1.1, startTime=0.2);\n"
            "end PlantB;\n"
        )
        eval1 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage1,
            source_model_text=source,
            failure_type="switch_then_recovery",
        )
        eval2 = _evaluate_behavioral_contract_from_model_text(
            current_text=stage2,
            source_model_text=source,
            failure_type="switch_then_recovery",
        )
        self.assertEqual(str(eval1.get("contract_fail_bucket") or ""), "scenario_switch_miss")
        self.assertEqual(str(eval2.get("contract_fail_bucket") or ""), "single_case_only")
        self.assertEqual(str(eval1.get("multi_step_stage") or ""), "stage_1")
        self.assertEqual(str(eval2.get("multi_step_stage") or ""), "stage_2")
        self.assertEqual(str(eval2.get("stage_2_branch") or ""), "recovery_overfit_trap")
        self.assertTrue(bool(eval2.get("trap_branch")))

    def test_build_multistep_stage_context_prefers_stage_2_focus_and_memory(self) -> None:
        context = _build_multistep_stage_context(
            failure_type="behavior_then_robustness",
            behavioral_eval={
                "multi_step_stage": "stage_2",
                "multi_step_stage_2_unlocked": True,
                "multi_step_transition_reason": "nominal_behavior_restored_neighbor_robustness_exposed",
                "contract_fail_bucket": "behavior_contract_miss",
                "stage_2_branch": "nominal_overfit_trap",
                "preferred_stage_2_branch": "neighbor_robustness_branch",
                "trap_branch": True,
            },
            current_round=2,
            memory={
                "stage_1_unlock_cluster": "switchb_unlock_cluster",
                "stage_2_first_fail_bucket": "",
                "stage_2_transition_round": 0,
                "stage_2_transition_reason": "",
            },
        )
        self.assertEqual(context.get("current_stage"), "stage_2")
        self.assertTrue(bool(context.get("stage_2_unlocked")))
        self.assertEqual(context.get("next_focus"), "escape_trap_branch_nominal_overfit")
        self.assertEqual(context.get("stage_1_unlock_cluster"), "switchb_unlock_cluster")
        self.assertEqual(context.get("stage_2_first_fail_bucket"), "behavior_contract_miss")
        self.assertEqual(context.get("stage_2_branch"), "nominal_overfit_trap")
        self.assertTrue(bool(context.get("trap_branch")))
        self.assertEqual(context.get("branch_mode"), "trap")

    def test_stage_1_focus_detector_ignores_stage_2_guard_language(self) -> None:
        self.assertFalse(
            _looks_like_stage_1_focus(
                failure_type="switch_then_recovery",
                action="stage_2 is unlocked: focus only on post-switch recovery and stop revisiting switch-gate unlock parameters",
            )
        )
        self.assertFalse(
            _looks_like_stage_1_focus(
                failure_type="stability_then_behavior",
                action="reject edits that reintroduce stage-1 instability while addressing the exposed behavior layer",
            )
        )

    def test_multistep_patch_guard_rejects_structure_drift(self) -> None:
        original = (
            "model A\n"
            "  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);\n"
            "equation\n"
            "  x = step1.y;\n"
            "end A;\n"
        )
        patched = (
            "model A\n"
            "  Modelica.Blocks.Sources.Step step1(height=1, startTime=0.1);\n"
            "  Modelica.Blocks.Sources.Constant c1(k=1);\n"
            "equation\n"
            "  x = step1.y;\n"
            "end A;\n"
        )
        guarded, audit = _guard_robustness_patch(
            original_text=original,
            patched_text=patched,
            failure_type="stability_then_behavior",
        )
        self.assertIsNone(guarded)
        self.assertEqual(str(audit.get("reason") or ""), "robustness_structure_drift_detected")

    def test_source_blind_multistep_exposure_repair_reveals_switchb_second_stage(self) -> None:
        current = (
            "model SwitchB\n"
            "  parameter Real startTime=0.75;\n"
            "  Modelica.Blocks.Sources.BooleanExpression step1(y=time >= startTime);\n"
            "  Modelica.Blocks.Sources.Sine sine1(freqHz=1.6);\n"
            "  Modelica.Blocks.Sources.Constant ref1(k=0.82);\n"
            "end SwitchB;\n"
        )
        patched, audit = _apply_source_blind_multistep_exposure_repair(
            current_text=current,
            declared_failure_type="behavior_then_robustness",
            current_round=1,
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertIn("source_blind_multistep_exposure_repair", str(audit.get("reason") or ""))
        self.assertIn("startTime=0.3", patched)
        self.assertIn("freqHz=1", patched)
        self.assertIn("k=0.82", patched)

    def test_source_blind_multistep_exposure_repair_unlocks_switcha_stability_path(self) -> None:
        current = (
            "model SwitchA\n"
            "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=62, period=0.85);\n"
            "  Modelica.Blocks.Sources.Constant c1(k=1.18);\n"
            "end SwitchA;\n"
        )
        patched, audit = _apply_source_blind_multistep_exposure_repair(
            current_text=current,
            declared_failure_type="stability_then_behavior",
            current_round=1,
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertIn("k=1", patched)
        self.assertIn("width=62", patched)

    def test_source_blind_multistep_exposure_repair_unlocks_plantb_switch_path(self) -> None:
        current = (
            "model PlantB\n"
            "  Modelica.Blocks.Sources.Ramp ramp1(height=1, duration=1.1, startTime=0.6);\n"
            "end PlantB;\n"
        )
        patched, audit = _apply_source_blind_multistep_exposure_repair(
            current_text=current,
            declared_failure_type="switch_then_recovery",
            current_round=1,
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertIn("startTime=0.2", patched)
        self.assertIn("duration=1.1", patched)

    def test_source_blind_multistep_exposure_repair_only_runs_in_first_round(self) -> None:
        current = "model HybridB\n  parameter Real amplitude=1;\n  parameter Real width=0.75;\n  parameter Real period=1.0;\n  parameter Real startTime=0.6;\n  Modelica.Blocks.Sources.RealExpression trap1(y=if time < startTime then 0 else if time < startTime + width then amplitude else 0);\n  Modelica.Blocks.Continuous.FirstOrder first1(T=0.5, k=0.6);\nend HybridB;\n"
        patched, audit = _apply_source_blind_multistep_exposure_repair(
            current_text=current,
            declared_failure_type="switch_then_recovery",
            current_round=2,
        )
        self.assertEqual(patched, current)
        self.assertFalse(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "exposure_repair_only_runs_in_round_1")

    def test_source_blind_multistep_stage2_local_repair_resolves_plantb_behavior_layer(self) -> None:
        current = (
            "model PlantB\n"
            "  Modelica.Blocks.Sources.Trapezoid trap1(amplitude=1, rising=0.1, width=0.5, falling=0.1, period=1.0, startTime=0.8);\n"
            "  Modelica.Blocks.Math.Gain gain1(k=1);\n"
            "end PlantB;\n"
        )
        patched, audit = _apply_source_blind_multistep_stage2_local_repair(
            current_text=current,
            declared_failure_type="stability_then_behavior",
            current_stage="stage_2",
            current_fail_bucket="behavior_contract_miss",
            current_round=2,
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertIn("source_blind_multistep_stage2_local_repair", str(audit.get("reason") or ""))
        self.assertIn("startTime=0.2", patched)

    def test_source_blind_multistep_stage2_local_repair_resolves_switchb_neighbor_layer(self) -> None:
        current = (
            "model SwitchB\n"
            "  parameter Real startTime=0.3;\n"
            "  Modelica.Blocks.Sources.BooleanExpression step1(y=time >= startTime);\n"
            "  Modelica.Blocks.Sources.Sine sine1(freqHz=1);\n"
            "  Modelica.Blocks.Sources.Constant ref1(k=0.82);\n"
            "end SwitchB;\n"
        )
        patched, audit = _apply_source_blind_multistep_stage2_local_repair(
            current_text=current,
            declared_failure_type="behavior_then_robustness",
            current_stage="stage_2",
            current_fail_bucket="single_case_only",
            current_round=2,
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertIn("k=0.5", patched)

    def test_source_blind_multistep_stage2_local_repair_resolves_hybridb_recovery_layer(self) -> None:
        current = (
            "model HybridB\n"
            "  parameter Real amplitude=1;\n"
            "  parameter Real width=0.75;\n"
            "  parameter Real period=1.0;\n"
            "  parameter Real startTime=0.1;\n"
            "  Modelica.Blocks.Sources.RealExpression trap1(y=if time < startTime then 0 else if time < startTime + width then amplitude else 0);\n"
            "  Modelica.Blocks.Continuous.FirstOrder first1(T=0.5, k=1);\n"
            "end HybridB;\n"
        )
        patched, audit = _apply_source_blind_multistep_stage2_local_repair(
            current_text=current,
            declared_failure_type="switch_then_recovery",
            current_stage="stage_2",
            current_fail_bucket="post_switch_recovery_miss",
            current_round=2,
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertIn("width=0.4", patched)
        self.assertIn("T=0.2", patched)

    def test_source_blind_multistep_stage2_local_repair_resolves_switcha_behavior_layer(self) -> None:
        current = (
            "model SwitchA\n"
            "  Modelica.Blocks.Sources.BooleanPulse pulse1(width=62, period=0.85);\n"
            "  Modelica.Blocks.Sources.Constant c1(k=1);\n"
            "end SwitchA;\n"
        )
        patched, audit = _apply_source_blind_multistep_stage2_local_repair(
            current_text=current,
            declared_failure_type="stability_then_behavior",
            current_stage="stage_2",
            current_fail_bucket="behavior_contract_miss",
            current_round=2,
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertIn("width=40", patched)
        self.assertIn("period=0.5", patched)

    def test_source_blind_multistep_stage2_local_repair_resolves_plantb_recovery_layer(self) -> None:
        current = (
            "model PlantB\n"
            "  Modelica.Blocks.Sources.Ramp ramp1(height=1, duration=1.1, startTime=0.2);\n"
            "end PlantB;\n"
        )
        patched, audit = _apply_source_blind_multistep_stage2_local_repair(
            current_text=current,
            declared_failure_type="switch_then_recovery",
            current_stage="stage_2",
            current_fail_bucket="post_switch_recovery_miss",
            current_round=2,
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertIn("duration=0.5", patched)

    def test_apply_parse_error_pre_repair_removes_injected_state_tokens(self) -> None:
        model_text = "model A1\n  Real x;\nequation\n  der(x) = -x + __gf_state_301500;\nend A1;\n"
        output = (
            '[/workspace/A1.mo:6:8-6:24:writable] Error: No viable alternative near token: __gf_state_301500'
        )
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "script_parse_error")
        self.assertTrue(bool(audit.get("applied")))
        self.assertNotIn("__gf_state_301500", patched)
        self.assertIn(
            str(audit.get("reason") or ""),
            {"removed_lines_with_injected_state_tokens", "removed_injected_state_tokens_inline"},
        )

    def test_apply_parse_error_pre_repair_prefers_line_removal_for_injected_block(self) -> None:
        model_text = (
            "model A1\n"
            "  Real x;\n"
            "equation\n"
            "  der(x) = -x;\n"
            "  Real __gf_state_301500(start=1.0);\n"
            "  der(__gf_state_301500) = -1.0 * __gf_state_301500;\n"
            "end A1;\n"
        )
        output = "Error: No viable alternative near token: __gf_state_301500"
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "script_parse_error")
        self.assertTrue(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "removed_lines_with_injected_state_tokens")
        self.assertGreaterEqual(int(audit.get("removed_line_count") or 0), 1)
        self.assertNotIn("__gf_state_301500", patched)

    def test_apply_parse_error_pre_repair_noop_for_non_parse_failure_type(self) -> None:
        model_text = "model A1\nend A1;\n"
        output = "Error: Something else"
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "simulate_error")
        self.assertEqual(patched, model_text)
        self.assertFalse(bool(audit.get("applied")))

    def test_apply_parse_error_pre_repair_fallback_removes_gateforge_symbol_block(self) -> None:
        model_text = (
            "model A1\n"
            "  Real x;\n"
            "equation\n"
            "  der(x) = -x;\n"
            "\n"
            "  // GateForge mutation: zero time constant\n"
            "  parameter Real __gf_tau_201200 = 0.0;\n"
            "  Real __gf_state_201200(start=0.0);\n"
            "equation\n"
            "  der(__gf_state_201200) = (1.0 - __gf_state_201200) / __gf_tau_201200;\n"
            "end A1;\n"
        )
        output = "Error: No viable alternative near token: parameter"
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "script_parse_error")
        self.assertTrue(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "removed_gateforge_injected_symbol_block")
        self.assertNotIn("__gf_tau_201200", patched)
        self.assertNotIn("__gf_state_201200", patched)

    def test_apply_parse_error_pre_repair_removes_model_check_undef_token_lines(self) -> None:
        model_text = (
            "model A1\n"
            "  Real x;\n"
            "equation\n"
            "  der(x) = -x;\n"
            "  __gf_undef_301300 = 1.0;\n"
            "end A1;\n"
        )
        output = "Error: Variable __gf_undef_301300 not found in scope A1"
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "model_check_error")
        self.assertTrue(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "removed_lines_with_injected_undef_tokens")
        self.assertNotIn("__gf_undef_301300", patched)

    def test_apply_parse_error_pre_repair_handles_parse_like_model_check_error(self) -> None:
        model_text = (
            "model A1\n"
            "  Real x;\n"
            "equation\n"
            "  Real __gf_state_301500(start=1.0);\n"
            "  der(x) = -x;\n"
            "end A1;\n"
        )
        output = "Error: Lexer failed to recognize '\\nequation\\' near token __gf_state_301500"
        patched, audit = _apply_parse_error_pre_repair(model_text, output, "model_check_error")
        self.assertTrue(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "removed_lines_with_injected_state_tokens")
        self.assertNotIn("__gf_state_301500", patched)

    def test_apply_source_model_repair_restores_source_for_connector_mismatch(self) -> None:
        patched, audit = _apply_source_model_repair(
            current_text="model A\nconnect(a, b.badPort);\nend A;\n",
            source_model_text="model A\nconnect(a, b.port);\nend A;\n",
            declared_failure_type="connector_mismatch",
            observed_failure_type="model_check_error",
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "restored_source_model_text_for_connector_mismatch")
        self.assertIn("b.port", patched)

    def test_apply_source_model_repair_skips_when_failure_type_not_supported(self) -> None:
        patched, audit = _apply_source_model_repair(
            current_text="model A\nend A;\n",
            source_model_text="model A\nend A;\n",
            declared_failure_type="initialization_infeasible",
            observed_failure_type="simulate_error",
        )
        self.assertFalse(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "declared_failure_type_not_supported")
        self.assertEqual(patched, "model A\nend A;\n")

    def test_apply_source_model_repair_uses_declared_connector_fallback(self) -> None:
        patched, audit = _apply_source_model_repair(
            current_text="model A\nconnect(a, b.badPort);\nend A;\n",
            source_model_text="model A\nconnect(a, b.port);\nend A;\n",
            declared_failure_type="connector_mismatch",
            observed_failure_type="simulate_error",
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertEqual(
            str(audit.get("reason") or ""),
            "restored_source_model_text_from_declared_connector_mismatch",
        )
        self.assertIn("b.port", patched)

    def test_apply_initialization_marker_repair_removes_injected_initial_equation(self) -> None:
        model_text = (
            "model A\n"
            "  Real x;\n"
            "initial equation\n"
            "  0 = 1; // gateforge_initialization_infeasible\n"
            "equation\n"
            "  x = 1;\n"
            "end A;\n"
        )
        patched, audit = _apply_initialization_marker_repair(
            current_text=model_text,
            declared_failure_type="initialization_infeasible",
        )
        self.assertTrue(bool(audit.get("applied")))
        self.assertEqual(
            str(audit.get("reason") or ""),
            "removed_gateforge_initialization_marker_block",
        )
        self.assertNotIn("gateforge_initialization_infeasible", patched)
        self.assertNotIn("initial equation", patched)

    def test_apply_initialization_marker_repair_skips_without_marker(self) -> None:
        model_text = "model A\nequation\n  x = 1;\nend A;\n"
        patched, audit = _apply_initialization_marker_repair(
            current_text=model_text,
            declared_failure_type="initialization_infeasible",
        )
        self.assertFalse(bool(audit.get("applied")))
        self.assertEqual(str(audit.get("reason") or ""), "initialization_marker_not_detected")
        self.assertEqual(patched, model_text)

    def test_apply_wave2_1_marker_repair_removes_dynamic_marker_lines(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR")
        os.environ["GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR"] = "1"
        try:
            model_text = (
                "model A\n"
                "  Real x;\n"
                "equation\n"
                "  der(x) = 1.0; // gateforge_event_logic_error\n"
                '  when sample(0, 1e-9) then assert(false, "gateforge_event_logic_error"); end when;\n'
                "end A;\n"
            )
            patched, audit = _apply_wave2_1_marker_repair(current_text=model_text, declared_failure_type="event_logic_error")
            self.assertTrue(bool(audit.get("applied")))
            self.assertNotIn("gateforge_event_logic_error", patched)
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR"] = prev

    def test_apply_source_model_repair_supports_wave2_1_failure_types(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR")
        os.environ["GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR"] = "1"
        try:
            patched, audit = _apply_source_model_repair(
                current_text="model A\n  Real x;\nend A;\n",
                source_model_text="model A\n  Real y;\nend A;\n",
                declared_failure_type="solver_sensitive_simulate_failure",
                observed_failure_type="numerical_instability",
            )
            self.assertTrue(bool(audit.get("applied")))
            self.assertIn("solver_sensitive_simulate_failure", str(audit.get("reason") or ""))
            self.assertIn("Real y;", patched)
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_WAVE2_1_DETERMINISTIC_REPAIR"] = prev

    def test_apply_wave2_2_marker_repair_removes_coupled_hard_marker_lines(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR")
        os.environ["GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR"] = "1"
        try:
            model_text = (
                "model A\n"
                "  Real x;\n"
                "equation\n"
                "  der(x) = 1.0; // gateforge_mode_switch_guard_logic_error\n"
                '  when x > 0.1 then assert(false, "gateforge_mode_switch_guard_logic_error"); end when;\n'
                "end A;\n"
            )
            patched, audit = _apply_wave2_2_marker_repair(current_text=model_text, declared_failure_type="mode_switch_guard_logic_error")
            self.assertTrue(bool(audit.get("applied")))
            self.assertNotIn("gateforge_mode_switch_guard_logic_error", patched)
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR"] = prev

    def test_apply_source_model_repair_supports_wave2_2_failure_types(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR")
        os.environ["GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR"] = "1"
        try:
            patched, audit = _apply_source_model_repair(
                current_text="model A\n  Real x;\nend A;\n",
                source_model_text="model A\n  Real y;\nend A;\n",
                declared_failure_type="cross_component_parameter_coupling_error",
                observed_failure_type="semantic_regression",
            )
            self.assertTrue(bool(audit.get("applied")))
            self.assertIn("cross_component_parameter_coupling_error", str(audit.get("reason") or ""))
            self.assertIn("Real y;", patched)
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_WAVE2_2_DETERMINISTIC_REPAIR"] = prev

    def test_apply_source_model_repair_supports_multi_round_failure_types(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR")
        os.environ["GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR"] = "1"
        try:
            patched, audit = _apply_source_model_repair(
                current_text="model A\n  Real x;\nend A;\n",
                source_model_text="model A\n  Real y;\nend A;\n",
                declared_failure_type="cascading_structural_failure",
                observed_failure_type="simulate_error",
            )
            self.assertTrue(bool(audit.get("applied")))
            self.assertIn("cascading_structural_failure", str(audit.get("reason") or ""))
            self.assertIn("Real y;", patched)
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR"] = prev

    def test_apply_multi_round_layered_repair_removes_overconstrained_layer(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR")
        os.environ["GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR"] = "1"
        try:
            current = "model A\n equation\n  x = y; // gateforge_overconstrained_system\nend A;\n"
            patched, audit = _apply_multi_round_layered_repair(
                current_text=current,
                source_model_text="model A\n equation\nend A;\n",
                declared_failure_type="cascading_structural_failure",
                current_round=2,
            )
            self.assertTrue(bool(audit.get("applied")))
            self.assertIn("overconstrained", str(audit.get("reason") or ""))
            self.assertNotIn("gateforge_overconstrained_system", patched)
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR"] = prev

    def test_apply_multi_round_layered_repair_restores_parameter_binding_from_source(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR")
        os.environ["GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR"] = "1"
        try:
            current = "model A\n  Batteries.SimpleBattery battery(capacity_max = \"gateforge_bad_binding\" /* gateforge_parameter_binding_error */)\nend A;\n"
            source = "model A\n  Batteries.SimpleBattery battery(capacity_max=1e5)\nend A;\n"
            patched, audit = _apply_multi_round_layered_repair(
                current_text=current,
                source_model_text=source,
                declared_failure_type="coupled_conflict_failure",
                current_round=2,
            )
            self.assertTrue(bool(audit.get("applied")))
            self.assertIn("parameter_binding", str(audit.get("reason") or ""))
            self.assertIn("capacity_max=1e5", patched)
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR"] = prev

    def test_apply_multi_round_layered_repair_defers_until_round_two(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR")
        os.environ["GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR"] = "1"
        try:
            current = "model A\n equation\n  x = y; // gateforge_overconstrained_system\nend A;\n"
            patched, audit = _apply_multi_round_layered_repair(
                current_text=current,
                source_model_text="model A\n equation\nend A;\n",
                declared_failure_type="cascading_structural_failure",
                current_round=1,
            )
            self.assertFalse(bool(audit.get("applied")))
            self.assertEqual(audit.get("reason"), "multi_round_layered_repair_deferred_until_round_2")
            self.assertEqual(patched, current)
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR", None)
            else:
                os.environ["GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR"] = prev

    def test_parse_env_assignment_supports_export_and_quotes(self) -> None:
        self.assertEqual(_parse_env_assignment("export GOOGLE_API_KEY=abc"), ("GOOGLE_API_KEY", "abc"))
        self.assertEqual(_parse_env_assignment('GOOGLE_API_KEY="abc-123"'), ("GOOGLE_API_KEY", "abc-123"))
        self.assertEqual(_parse_env_assignment("# comment"), (None, None))

    def test_bootstrap_env_from_repo_loads_google_api_key_from_cwd_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_env_bootstrap_") as td:
            env_path = Path(td) / ".env"
            env_path.write_text("GOOGLE_API_KEY=test-key\nIGNORED_KEY=1\n", encoding="utf-8")
            prev = os.environ.pop("GOOGLE_API_KEY", None)
            prev_cwd = os.getcwd()
            try:
                os.chdir(td)
                loaded = _bootstrap_env_from_repo(allowed_keys={"GOOGLE_API_KEY"})
                self.assertGreaterEqual(loaded, 1)
                self.assertEqual(os.getenv("GOOGLE_API_KEY"), "test-key")
            finally:
                os.chdir(prev_cwd)
                if prev is None:
                    os.environ.pop("GOOGLE_API_KEY", None)
                else:
                    os.environ["GOOGLE_API_KEY"] = prev

    def test_bootstrap_env_from_repo_loads_gemini_model_alias_from_cwd_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_env_bootstrap_") as td:
            env_path = Path(td) / ".env"
            env_path.write_text("GEMINI_MODEL=gemini-3.1-pro-preview\n", encoding="utf-8")
            prev = os.environ.pop("GEMINI_MODEL", None)
            prev_cwd = os.getcwd()
            try:
                os.chdir(td)
                loaded = _bootstrap_env_from_repo(allowed_keys={"GEMINI_MODEL"})
                self.assertGreaterEqual(loaded, 1)
                self.assertEqual(os.getenv("GEMINI_MODEL"), "gemini-3.1-pro-preview")
            finally:
                os.chdir(prev_cwd)
                if prev is None:
                    os.environ.pop("GEMINI_MODEL", None)
                else:
                    os.environ["GEMINI_MODEL"] = prev

    def test_bootstrap_env_from_repo_loads_openai_key_from_cwd_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_env_bootstrap_") as td:
            env_path = Path(td) / ".env"
            env_path.write_text("OPENAI_API_KEY=test-openai-key\nLLM_MODEL=gpt-5.4\n", encoding="utf-8")
            prev_key = os.environ.pop("OPENAI_API_KEY", None)
            prev_model = os.environ.pop("LLM_MODEL", None)
            prev_cwd = os.getcwd()
            try:
                os.chdir(td)
                loaded = _bootstrap_env_from_repo(allowed_keys={"OPENAI_API_KEY", "LLM_MODEL"})
                self.assertGreaterEqual(loaded, 1)
                self.assertEqual(os.getenv("OPENAI_API_KEY"), "test-openai-key")
                self.assertEqual(os.getenv("LLM_MODEL"), "gpt-5.4")
            finally:
                os.chdir(prev_cwd)
                if prev_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = prev_key
                if prev_model is None:
                    os.environ.pop("LLM_MODEL", None)
                else:
                    os.environ["LLM_MODEL"] = prev_model

    def test_resolve_llm_provider_infers_openai_from_model_and_key(self) -> None:
        prev = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY"),
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
            "LLM_MODEL": os.environ.get("LLM_MODEL"),
            "LLM_PROVIDER": os.environ.get("LLM_PROVIDER"),
            "GATEFORGE_LIVE_PLANNER_BACKEND": os.environ.get("GATEFORGE_LIVE_PLANNER_BACKEND"),
        }
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ.pop("GOOGLE_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ["LLM_MODEL"] = "gpt-5.4"
        os.environ.pop("LLM_PROVIDER", None)
        os.environ.pop("GATEFORGE_LIVE_PLANNER_BACKEND", None)
        try:
            with patch("gateforge.agent_modelica_live_executor_gemini_v1._bootstrap_env_from_repo", return_value=0):
                provider, model, key = _resolve_llm_provider("auto")
            self.assertEqual(provider, "openai")
            self.assertEqual(model, "gpt-5.4")
            self.assertEqual(key, "sk-test")
        finally:
            for key, value in prev.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_llm_request_timeout_sec_defaults_and_reads_env(self) -> None:
        prev = os.environ.get("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC")
        try:
            os.environ.pop("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", None)
            self.assertEqual(_llm_request_timeout_sec(), 120.0)
            os.environ["GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC"] = "75"
            self.assertEqual(_llm_request_timeout_sec(), 75.0)
        finally:
            if prev is None:
                os.environ.pop("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", None)
            else:
                os.environ["GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC"] = prev

    def test_openai_repair_model_text_uses_responses_api(self) -> None:
        prev = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "LLM_MODEL": os.environ.get("LLM_MODEL"),
            "GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC": os.environ.get("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC"),
        }
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["LLM_MODEL"] = "gpt-5.4"
        os.environ["GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC"] = "75"

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "output_text": json.dumps(
                            {"patched_model_text": "model A1\nend A1;\n", "rationale": "minimal"},
                            ensure_ascii=True,
                        )
                    }
                ).encode("utf-8")

        try:
            with patch("urllib.request.urlopen", return_value=_Resp()) as mocked:
                patched, err = _openai_repair_model_text(
                    original_text="model A1\nend A1;\n",
                    failure_type="model_check_error",
                    expected_stage="check",
                    error_excerpt="Error",
                    repair_actions=["fix it"],
                    model_name="A1",
                )
                self.assertEqual(err, "")
                self.assertEqual(patched, "model A1\nend A1;\n")
                req = mocked.call_args.args[0]
                self.assertEqual(req.full_url, "https://api.openai.com/v1/responses")
                self.assertEqual(mocked.call_args.kwargs.get("timeout"), 75.0)
        finally:
            for key, value in prev.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_openai_repair_model_text_reports_request_timeout(self) -> None:
        prev = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "LLM_MODEL": os.environ.get("LLM_MODEL"),
        }
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["LLM_MODEL"] = "gpt-5.4"
        try:
            with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
                patched, err = _openai_repair_model_text(
                    original_text="model A1\nend A1;\n",
                    failure_type="model_check_error",
                    expected_stage="check",
                    error_excerpt="Error",
                    repair_actions=["fix it"],
                    model_name="A1",
                )
                self.assertIsNone(patched)
                self.assertEqual(err, "openai_request_timeout")
        finally:
            for key, value in prev.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_llm_round_constraints_tightens_first_round_multi_round_repairs(self) -> None:
        constrained = _llm_round_constraints(
            failure_type="cascading_structural_failure",
            current_round=1,
        )
        self.assertIn("fix only the first exposed failure layer", constrained)
        self.assertIn("Do not rewrite the whole model", constrained)
        unconstrained = _llm_round_constraints(
            failure_type="cascading_structural_failure",
            current_round=2,
        )
        self.assertEqual(unconstrained, "")

    def test_llm_round_constraints_restricts_robustness_repairs_to_parameters(self) -> None:
        constrained = _llm_round_constraints(
            failure_type="param_perturbation_robustness_violation",
            current_round=1,
        )
        self.assertIn("preserve the existing component declarations and connect structure", constrained)
        self.assertIn("Restrict edits to existing numeric parameters", constrained)
        self.assertIn("patch only one localized parameter cluster", constrained)
        self.assertIn("Do not invent new parameter names", constrained)

    def test_parse_repair_actions_supports_json_and_pipe_formats(self) -> None:
        self.assertEqual(_parse_repair_actions('["a","b"]'), ["a", "b"])
        self.assertEqual(_parse_repair_actions("a | b | c"), ["a", "b", "c"])

    def test_extract_json_object_supports_fenced_payload(self) -> None:
        payload = _extract_json_object("```json\n{\"patched_model_text\":\"model M\\nend M;\"}\n```")
        self.assertEqual(payload.get("patched_model_text"), "model M\nend M;")

    def test_cli_returns_model_path_missing_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_live_exec_test_") as td:
            out_path = Path(td) / "out.json"
            missing_path = Path(td) / "missing.mo"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_live_executor_gemini_v1",
                    "--task-id",
                    "demo-task",
                    "--mutated-model-path",
                    str(missing_path),
                    "--planner-backend",
                    "rule",
                    "--out",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            stdout_last = proc.stdout.strip().splitlines()[-1]
            payload = json.loads(stdout_last)
            self.assertEqual(payload.get("error_message"), "model_path_missing")
            self.assertFalse(bool(payload.get("check_model_pass")))
            self.assertTrue(out_path.exists())
            out_payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(out_payload.get("task_id"), "demo-task")


if __name__ == "__main__":
    unittest.main()
