from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _simple_runtime_model(model_name: str, *, param_names: tuple[str, str, str]) -> str:
    p1, p2, p3 = param_names
    return "\n".join(
        [
            f"model {model_name}",
            f"  parameter Real {p1} = 1.0;",
            f"  parameter Real {p2} = 2.0;",
            f"  parameter Real {p3} = 3.0;",
            "  Real x(start = 1.0);",
            "equation",
            f"  der(x) = -({p1} + {p2}) * x + {p3};",
            f"end {model_name};",
        ]
    )


def _simple_init_model(model_name: str, *, lhs_names: tuple[str, str]) -> str:
    lhs1, lhs2 = lhs_names
    return "\n".join(
        [
            f"model {model_name}",
            f"  Real {lhs1}(start = 2.0);",
            f"  Real {lhs2}(start = 4.0);",
            "initial equation",
            f"  {lhs1} = 2.0;",
            f"  {lhs2} = 4.0;",
            "equation",
            f"  der({lhs1}) = 1.0 - sqrt({lhs1});",
            f"  der({lhs2}) = 0.5 * sqrt({lhs2}) * (1.0 - {lhs2} / 9.0);",
            f"end {model_name};",
        ]
    )


def _attempt(
    *,
    round_idx: int,
    stage_subtype: str,
    error_subtype: str,
    observed_failure_type: str,
    reason: str,
    action_name: str,
    rule_tier: str,
    check_model_pass: bool,
    simulate_pass: bool,
) -> dict:
    return {
        "round": round_idx,
        "observed_failure_type": observed_failure_type,
        "reason": reason,
        "diagnostic_ir": {
            "dominant_stage_subtype": stage_subtype,
            "error_subtype": error_subtype,
        },
        "check_model_pass": check_model_pass,
        "simulate_pass": simulate_pass,
        action_name: {
            "applied": True,
            "rule_id": f"rule_{action_name}",
            "action_key": f"repair|{action_name}",
            "rule_tier": rule_tier,
            "replay_eligible": True,
            "failure_bucket_before": "before",
            "failure_bucket_after": "after",
        },
    }


def _success_result_detail(
    *,
    stage_subtype: str,
    error_subtype: str,
    observed_failure_type: str,
    reason: str,
    action_sequence: list[str],
    final_check_pass: bool = True,
    final_simulate_pass: bool = True,
    planner_event_count: int = 1,
) -> dict:
    attempts: list[dict] = []
    for idx, action_name in enumerate(action_sequence, start=1):
        attempts.append(
            _attempt(
                round_idx=idx,
                stage_subtype=stage_subtype,
                error_subtype=error_subtype,
                observed_failure_type=observed_failure_type,
                reason=reason,
                action_name=action_name,
                rule_tier="planner" if "parameter_recovery" in action_name else "deterministic",
                check_model_pass=stage_subtype != "stage_1_parse_syntax",
                simulate_pass=False,
            )
        )
    return {
        "executor_status": "PASS",
        "resolution_path": "rule_then_llm",
        "rounds_used": len(attempts) + 1,
        "check_model_pass": final_check_pass,
        "simulate_pass": final_simulate_pass,
        "failure_type": observed_failure_type,
        "dominant_stage_subtype": stage_subtype,
        "executor_runtime_hygiene": {
            "planner_event_count": planner_event_count,
        },
        "attempts": attempts,
    }


def _failure_result_detail(
    *,
    stage_subtype: str,
    error_subtype: str,
    observed_failure_type: str,
    reason: str,
    attempt_count: int,
) -> dict:
    attempts = []
    for idx in range(1, attempt_count + 1):
        action_name = "simulate_error_parameter_recovery" if idx > 1 else "simulate_error_injection_repair"
        attempts.append(
            _attempt(
                round_idx=idx,
                stage_subtype=stage_subtype,
                error_subtype=error_subtype,
                observed_failure_type=observed_failure_type,
                reason=reason,
                action_name=action_name,
                rule_tier="planner" if idx > 1 else "deterministic",
                check_model_pass=True,
                simulate_pass=False,
            )
        )
    return {
        "executor_status": "FAIL",
        "resolution_path": "unresolved_after_multiround",
        "rounds_used": attempt_count,
        "check_model_pass": True,
        "simulate_pass": False,
        "failure_type": observed_failure_type,
        "dominant_stage_subtype": stage_subtype,
        "executor_runtime_hygiene": {
            "planner_event_count": max(1, attempt_count - 1),
        },
        "attempts": attempts,
    }


def v0314_fixture_step_store_payload() -> dict:
    rows = []
    for idx in range(6):
        rows.append(
            {
                "task_id": f"fixture_runtime_{idx}",
                "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
                "residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
                "action_type": "simulate_error_parameter_recovery",
                "step_outcome": "advancing",
            }
        )
    for idx in range(2):
        rows.append(
            {
                "task_id": f"fixture_init_{idx}",
                "dominant_stage_subtype": "stage_4_initialization_singularity",
                "residual_signal_cluster": "stage_4_initialization_singularity|init_failure",
                "action_type": "simulate_error_parameter_recovery",
                "step_outcome": "advancing",
            }
        )
    for idx in range(2):
        rows.append(
            {
                "task_id": f"fixture_parse_{idx}",
                "dominant_stage_subtype": "stage_1_parse_syntax",
                "residual_signal_cluster": "stage_1_parse_syntax|parse_lexer_error",
                "action_type": "parse_error_cleanup_repair",
                "step_outcome": "advancing",
            }
        )
    return {
        "schema_version": "agent_modelica_v0_3_14_experience_store",
        "generated_at_utc": _now_utc(),
        "step_records": rows,
    }


def v0315_runtime_source_manifest_payload() -> dict:
    specs = [
        ("v036_rlc_dual_collapse__pair_r_c__preview", "FixtureRlcRC", ("R", "C", "L")),
        ("v036_rlc_dual_collapse__pair_l_c__preview", "FixtureRlcLC", ("L", "C", "R")),
        ("v036_heater_dual_collapse__pair_c_q__preview", "FixtureHeaterCQ", ("C", "Q", "Tenv")),
        ("v036_heater_dual_collapse__pair_c_tenv__preview", "FixtureHeaterCT", ("C", "Tenv", "Q")),
        ("v036_thermal_rc_dual_collapse__pair_cth_tenv__preview", "FixtureThermalCT", ("Cth", "Tenv", "Rth")),
        ("v036_hydraulic_ar_dual_collapse__pair_a_qin__preview", "FixtureHydraulicAQ", ("A", "Qin", "R")),
        ("v036_mix_vtau_dual_collapse__pair_v_cin__preview", "FixtureMixVC", ("V", "Cin", "Tau")),
    ]
    sources = []
    for task_id, model_name, params in specs:
        sources.append(
            {
                "source_task_id": task_id,
                "source_model_path": f"gateforge/source_models/fixtures/{model_name}.mo",
                "source_library": "GateForge_fixture_runtime",
                "model_hint": model_name,
                "clean_model_text": _simple_runtime_model(model_name, param_names=params),
            }
        )
    return {
        "schema_version": "agent_modelica_v0_3_13_runtime_generation_source",
        "generated_at_utc": _now_utc(),
        "source_count": len(sources),
        "sources": sources,
    }


def v0316_drift_rows_payload() -> list[dict]:
    rows = []
    for source_id in ("fixture_runtime_a", "fixture_runtime_b", "fixture_runtime_c"):
        rows.append(
            {
                "task_id": f"{source_id}__drift",
                "source_family_id": "runtime_same_cluster_harder_variant",
                "source_identity": source_id,
                "hidden_base_operator": "multi_value_collapse",
                "target_count": 3,
                "live_stage_subtype": "stage_2_structural_balance_reference",
                "live_residual_signal_cluster": "stage_2_structural_balance_reference",
                "exact_match_available": False,
                "baseline_verdict": "FAIL",
            }
        )
    for source_id in ("fixture_init_a", "fixture_init_b"):
        rows.append(
            {
                "task_id": f"{source_id}__drift",
                "source_family_id": "initialization_same_cluster_harder_variant",
                "source_identity": source_id,
                "hidden_base_operator": "multi_target_init_equation_sign_flip",
                "target_count": 2,
                "live_stage_subtype": "stage_2_structural_balance_reference",
                "live_residual_signal_cluster": "stage_2_structural_balance_reference",
                "exact_match_available": False,
                "baseline_verdict": "FAIL",
            }
        )
    return rows


def v0316_probe_control_tasks_payload() -> list[dict]:
    return [
        {
            "task_id": "v036_rlc_dual_collapse__pair_r_c__preview",
            "v0_3_16_probe_lane_name": "runtime_preservation_control_lane",
            "v0_3_16_expected_stage_subtype": "stage_5_runtime_numerical_instability",
            "v0_3_16_expected_residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
        },
        {
            "task_id": "v036_heater_dual_collapse__pair_c_q__preview",
            "v0_3_16_probe_lane_name": "runtime_preservation_control_lane",
            "v0_3_16_expected_stage_subtype": "stage_5_runtime_numerical_instability",
            "v0_3_16_expected_residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
        },
        {
            "task_id": "init_log_sqrt__lhs_x__preview",
            "v0_3_16_probe_lane_name": "initialization_preservation_control_lane",
            "v0_3_16_expected_stage_subtype": "stage_4_initialization_singularity",
            "v0_3_16_expected_residual_signal_cluster": "stage_4_initialization_singularity|init_failure",
        },
        {
            "task_id": "init_log_growth__lhs_y__preview",
            "v0_3_16_probe_lane_name": "initialization_preservation_control_lane",
            "v0_3_16_expected_stage_subtype": "stage_4_initialization_singularity",
            "v0_3_16_expected_residual_signal_cluster": "stage_4_initialization_singularity|init_failure",
        },
    ]


def materialize_v0314_authority_fixture(out_dir: str | Path) -> dict[str, str]:
    from .agent_modelica_v0_3_14_authority_manifest import (
        INITIALIZATION_EVAL_TASK_IDS,
        INITIALIZATION_TRAIN_TASK_IDS,
        RUNTIME_EVAL_TASK_IDS,
        RUNTIME_TRAIN_TASK_IDS,
    )

    out_root = Path(out_dir)
    fixture_root = out_root / "_fixture_inputs"
    tasks_root = fixture_root / "tasks"
    results_root = fixture_root / "results"
    runtime_taskset_path = fixture_root / "runtime_taskset.json"
    runtime_live_summary_path = fixture_root / "runtime_live_summary.json"
    initialization_taskset_path = fixture_root / "initialization_taskset.json"
    initialization_live_summary_path = fixture_root / "initialization_live_summary.json"
    runtime_work_order_path = fixture_root / "runtime_work_order.json"
    initialization_work_order_path = fixture_root / "initialization_work_order.json"

    runtime_tasks = []
    all_runtime_ids = list(RUNTIME_TRAIN_TASK_IDS) + list(RUNTIME_EVAL_TASK_IDS)
    for idx, task_id in enumerate(all_runtime_ids, start=1):
        model_name = f"FixtureRuntimeModel{idx}"
        task_path = tasks_root / f"{task_id}.json"
        task_payload = {
            "task_id": task_id,
            "task_json_path": str(task_path.resolve()),
            "source_model_path": f"gateforge/source_models/fixtures/{model_name}.mo",
            "source_library": "GateForge_fixture_runtime",
            "model_hint": model_name,
            "mutation_spec": {
                "hidden_base": {
                    "operator": "multi_value_collapse",
                    "audit": {
                        "target_param_names": ["A", "B", "C"],
                    },
                }
            },
        }
        _write_json(task_path, task_payload)
        runtime_tasks.append(task_payload)

    initialization_tasks = []
    all_init_ids = list(INITIALIZATION_TRAIN_TASK_IDS) + list(INITIALIZATION_EVAL_TASK_IDS)
    for idx, task_id in enumerate(all_init_ids, start=1):
        model_name = f"FixtureInitModel{idx}"
        task_path = tasks_root / f"{task_id}.json"
        task_payload = {
            "task_id": task_id,
            "task_json_path": str(task_path.resolve()),
            "source_model_path": f"gateforge/source_models/fixtures/{model_name}.mo",
            "source_library": "GateForge_fixture_init",
            "model_hint": model_name,
            "mutation_spec": {
                "hidden_base": {
                    "operator": "init_equation_sign_flip",
                    "audit": {
                        "target_lhs_names": ["x", "y"],
                    },
                }
            },
        }
        _write_json(task_path, task_payload)
        initialization_tasks.append(task_payload)

    _write_json(runtime_taskset_path, {"tasks": runtime_tasks})
    _write_json(initialization_taskset_path, {"tasks": initialization_tasks})
    _write_json(runtime_work_order_path, {"runtime_lane_status": "LIVE_EVIDENCE_READY"})
    _write_json(initialization_work_order_path, {"initialization_lane_status": "LIVE_EVIDENCE_READY"})

    runtime_results = []
    for task_id in all_runtime_ids:
        detail_path = results_root / f"{task_id}_result.json"
        detail = _success_result_detail(
            stage_subtype="stage_5_runtime_numerical_instability",
            error_subtype="division_by_zero",
            observed_failure_type="numerical_instability",
            reason="division by zero in residual",
            action_sequence=[
                "simulate_error_injection_repair",
                "simulate_error_parameter_recovery",
            ] if task_id in RUNTIME_TRAIN_TASK_IDS else ["simulate_error_parameter_recovery"],
            planner_event_count=2 if task_id == "v036_rlc_dual_collapse__pair_l_c__preview" else 1,
        )
        _write_json(detail_path, detail)
        runtime_results.append(
            {
                "task_id": task_id,
                "verdict": "PASS",
                "result_json_path": str(detail_path.resolve()),
                "rounds_used": int(detail["rounds_used"]),
                "resolution_path": str(detail["resolution_path"]),
                "planner_event_count": int((detail.get("executor_runtime_hygiene") or {}).get("planner_event_count") or 0),
                "v0_3_13_source_task_id": task_id.replace("__preview", ""),
                "v0_3_13_candidate_pair": ["A", "B"],
            }
        )

    for idx in range(1, 6):
        task_id = f"runtime_failure_bank_case_{idx}"
        detail_path = results_root / f"{task_id}_result.json"
        detail = _failure_result_detail(
            stage_subtype="stage_2_structural_balance_reference",
            error_subtype="structural_singularity",
            observed_failure_type="simulate_error",
            reason="structurally singular system",
            attempt_count=8,
        )
        _write_json(detail_path, detail)
        runtime_results.append(
            {
                "task_id": task_id,
                "verdict": "FAIL",
                "result_json_path": str(detail_path.resolve()),
                "rounds_used": int(detail["rounds_used"]),
                "resolution_path": str(detail["resolution_path"]),
                "planner_event_count": int((detail.get("executor_runtime_hygiene") or {}).get("planner_event_count") or 0),
                "v0_3_13_source_task_id": task_id,
            }
        )

    initialization_results = []
    for task_id in all_init_ids:
        detail_path = results_root / f"{task_id}_result.json"
        if task_id == "init_dual_sqrt__lhs_x_fast__preview":
            detail = _success_result_detail(
                stage_subtype="stage_1_parse_syntax",
                error_subtype="parse_lexer_error",
                observed_failure_type="parse_error",
                reason="lexer error near injected marker",
                action_sequence=["parse_error_cleanup_repair", "simulate_error_parameter_recovery"],
                final_check_pass=True,
                final_simulate_pass=True,
                planner_event_count=1,
            )
        else:
            detail = _success_result_detail(
                stage_subtype="stage_4_initialization_singularity",
                error_subtype="init_failure",
                observed_failure_type="simulate_error",
                reason="initialization failed due to singular initial conditions",
                action_sequence=[
                    "simulate_error_injection_repair",
                    "simulate_error_parameter_recovery",
                ] if task_id in INITIALIZATION_TRAIN_TASK_IDS else ["simulate_error_parameter_recovery"],
                planner_event_count=1,
            )
        _write_json(detail_path, detail)
        initialization_results.append(
            {
                "task_id": task_id,
                "verdict": "PASS",
                "result_json_path": str(detail_path.resolve()),
                "rounds_used": int(detail["rounds_used"]),
                "resolution_path": str(detail["resolution_path"]),
                "planner_event_count": int((detail.get("executor_runtime_hygiene") or {}).get("planner_event_count") or 0),
                "v0_3_13_source_id": task_id.replace("__preview", ""),
                "v0_3_13_initialization_target_lhs": "x" if "x" in task_id else "y",
            }
        )

    _write_json(runtime_live_summary_path, {"results": runtime_results})
    _write_json(initialization_live_summary_path, {"results": initialization_results})
    return {
        "runtime_work_order_path": str(runtime_work_order_path),
        "runtime_taskset_path": str(runtime_taskset_path),
        "runtime_live_summary_path": str(runtime_live_summary_path),
        "initialization_work_order_path": str(initialization_work_order_path),
        "initialization_taskset_path": str(initialization_taskset_path),
        "initialization_live_summary_path": str(initialization_live_summary_path),
    }
