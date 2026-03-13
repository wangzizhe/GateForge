import unittest
import json

from gateforge.agent_modelica_realism_summary_v1 import build_realism_summary_v1


class AgentModelicaRealismSummaryV1Tests(unittest.TestCase):
    def test_build_realism_summary_reports_pass_for_aligned_wave1_taxonomy(self) -> None:
        summary = build_realism_summary_v1(
            evidence_summary={
                "pack_id": "agent_modelica_realism_pack_v1",
                "pack_version": "v1",
                "pack_track": "realism",
                "acceptance_scope": "independent_validation",
                "acceptance_mode": "absolute_non_regression",
            },
            challenge_summary={
                "pack_id": "agent_modelica_realism_pack_v1",
                "pack_version": "v1",
                "pack_track": "realism",
                "acceptance_scope": "independent_validation",
                "counts_by_failure_type": {
                    "underconstrained_system": 1,
                    "connector_mismatch": 1,
                    "initialization_infeasible": 1,
                },
                "counts_by_category": {
                    "topology_wiring": 2,
                    "initialization": 1,
                },
            },
            challenge_manifest={
                "baseline_provenance": {
                    "planner_backend": "gemini",
                    "llm_model": "gemini-3.1-pro-preview",
                    "backend": "openmodelica_docker",
                    "docker_image": "openmodelica/openmodelica:v1.26.1-minimal",
                    "max_rounds": 2,
                    "max_time_sec": 90,
                }
            },
            taskset_payload={
                "tasks": [
                    {
                        "task_id": "t_under",
                        "failure_type": "underconstrained_system",
                        "category": "topology_wiring",
                        "expected_stage": "check",
                    },
                    {
                        "task_id": "t_conn",
                        "failure_type": "connector_mismatch",
                        "category": "topology_wiring",
                        "expected_stage": "check",
                    },
                    {
                        "task_id": "t_init",
                        "failure_type": "initialization_infeasible",
                        "category": "initialization",
                        "expected_stage": "simulate",
                    },
                ]
            },
            l3_run_results={
                "records": [
                    {
                        "task_id": "t_under",
                        "attempts": [
                            {
                                "observed_failure_type": "model_check_error",
                                "diagnostic_ir": {
                                    "error_type": "model_check_error",
                                    "error_subtype": "compile_failure_unknown",
                                    "stage": "check",
                                    "observed_phase": "check",
                                },
                            }
                        ],
                    },
                    {
                        "task_id": "t_conn",
                        "attempts": [
                            {
                                "observed_failure_type": "model_check_error",
                                "diagnostic_ir": {
                                    "error_type": "model_check_error",
                                    "error_subtype": "connector_mismatch",
                                    "stage": "check",
                                    "observed_phase": "check",
                                },
                            }
                        ],
                    },
                    {
                        "task_id": "t_init",
                        "attempts": [
                            {
                                "observed_failure_type": "simulate_error",
                                "diagnostic_ir": {
                                    "error_type": "simulate_error",
                                    "error_subtype": "init_failure",
                                    "stage": "simulate",
                                    "observed_phase": "simulate",
                                },
                            }
                        ],
                    },
                ]
            },
            l3_quality_summary={
                "category_distribution": {
                    "topology_wiring": 2,
                    "initialization": 1,
                },
                "subtype_distribution": {
                    "compile_failure_unknown": 1,
                    "connector_mismatch": 1,
                    "init_failure": 1,
                },
            },
            l4_ab_compare_summary={},
            l5_summary={
                "gate_result": "PASS",
                "success_at_k_pct": 100.0,
                "failure_type_breakdown_on": {
                    "underconstrained_system": {"record_count": 1, "success_count": 1},
                    "connector_mismatch": {"record_count": 1, "success_count": 1},
                    "initialization_infeasible": {"record_count": 1, "success_count": 1},
                },
                "category_breakdown_on": {
                    "topology_wiring": {"record_count": 2, "success_count": 2},
                    "initialization": {"record_count": 1, "success_count": 1},
                },
            },
        )
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(summary.get("recommendation"), "ready_for_next_realism_iteration")
        self.assertEqual(summary.get("taxonomy_view_mode"), "dual_view")
        manifestation = summary.get("failure_manifestation_view") if isinstance(summary.get("failure_manifestation_view"), dict) else {}
        outcome = summary.get("final_outcome_view") if isinstance(summary.get("final_outcome_view"), dict) else {}
        self.assertEqual(manifestation.get("status"), "PASS")
        self.assertEqual(outcome.get("status"), "PASS")
        mismatch = summary.get("mismatch_summary") if isinstance(summary.get("mismatch_summary"), dict) else {}
        self.assertEqual(int(mismatch.get("initialization_truncated_by_check_count") or 0), 0)
        self.assertEqual(float(mismatch.get("connector_subtype_match_rate_pct") or 0.0), 100.0)
        self.assertEqual(float(mismatch.get("initialization_simulate_stage_rate_pct") or 0.0), 100.0)
        self.assertEqual(int(mismatch.get("missing_failure_signal_count") or 0), 0)
        self.assertEqual(int(mismatch.get("phase_drift_count") or 0), 0)

    def test_build_realism_summary_flags_initialization_truncation_for_wave1_repair(self) -> None:
        summary = build_realism_summary_v1(
            evidence_summary={},
            challenge_summary={
                "counts_by_failure_type": {"initialization_infeasible": 1},
                "counts_by_category": {"initialization": 1},
            },
            challenge_manifest={},
            taskset_payload={
                "tasks": [
                    {
                        "task_id": "t_init",
                        "failure_type": "initialization_infeasible",
                        "category": "initialization",
                        "expected_stage": "simulate",
                    }
                ]
            },
            l3_run_results={
                "records": [
                    {
                        "task_id": "t_init",
                        "attempts": [
                            {
                                "observed_failure_type": "model_check_error",
                                "diagnostic_ir": {
                                    "error_type": "model_check_error",
                                    "error_subtype": "undefined_symbol",
                                    "stage": "check",
                                    "observed_phase": "check",
                                },
                            }
                        ],
                    }
                ]
            },
            l3_quality_summary={
                "category_distribution": {"initialization": 1},
                "subtype_distribution": {"undefined_symbol": 1},
            },
            l4_ab_compare_summary={},
            l5_summary={
                "gate_result": "PASS",
                "success_at_k_pct": 0.0,
                "failure_type_breakdown_on": {
                    "initialization_infeasible": {"record_count": 1, "success_count": 0},
                },
                "category_breakdown_on": {
                    "initialization": {"record_count": 1, "success_count": 0},
                },
            },
        )
        self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
        self.assertEqual(summary.get("recommendation"), "repair_wave1_mutations")
        mismatch = summary.get("mismatch_summary") if isinstance(summary.get("mismatch_summary"), dict) else {}
        self.assertEqual(int(mismatch.get("initialization_truncated_by_check_count") or 0), 1)
        self.assertEqual(float(mismatch.get("initialization_simulate_stage_rate_pct") or 0.0), 0.0)

    def test_build_realism_summary_blocks_when_l5_is_budget_stopped(self) -> None:
        summary = build_realism_summary_v1(
            evidence_summary={},
            challenge_summary={
                "counts_by_failure_type": {"underconstrained_system": 1},
                "counts_by_category": {"topology_wiring": 1},
            },
            challenge_manifest={},
            taskset_payload={
                "tasks": [
                    {
                        "task_id": "t_under",
                        "failure_type": "underconstrained_system",
                        "category": "topology_wiring",
                        "expected_stage": "check",
                    }
                ]
            },
            l3_run_results={
                "records": [
                    {
                        "task_id": "t_under",
                        "attempts": [
                            {
                                "observed_failure_type": "model_check_error",
                                "diagnostic_ir": {
                                    "error_type": "model_check_error",
                                    "error_subtype": "underconstrained_system",
                                    "stage": "check",
                                    "observed_phase": "check",
                                },
                            }
                        ],
                    }
                ]
            },
            l3_quality_summary={
                "category_distribution": {"topology_wiring": 1},
                "subtype_distribution": {"underconstrained_system": 1},
            },
            l4_ab_compare_summary={},
            l5_summary={
                "status": "FAIL",
                "gate_result": "FAIL",
                "primary_reason": "live_request_budget_exceeded",
                "reasons": ["live_request_budget_exceeded", "run_results_missing"],
            },
        )
        self.assertEqual(summary.get("status"), "BLOCKED")
        self.assertEqual(summary.get("recommendation"), "blocked_missing_realism_inputs")
        self.assertIn("live_request_budget_exceeded", summary.get("reasons") or [])

    def test_build_realism_summary_uses_manifestation_for_resolved_tasks(self) -> None:
        summary = build_realism_summary_v1(
            evidence_summary={},
            challenge_summary={
                "counts_by_failure_type": {"underconstrained_system": 1},
                "counts_by_category": {"topology_wiring": 1},
            },
            challenge_manifest={},
            taskset_payload={
                "tasks": [
                    {
                        "task_id": "t_under",
                        "failure_type": "underconstrained_system",
                        "category": "topology_wiring",
                        "expected_stage": "check",
                    }
                ]
            },
            l3_run_results={
                "records": [
                    {
                        "task_id": "t_under",
                        "passed": True,
                        "attempts": [
                            {
                                "observed_failure_type": "model_check_error",
                                "diagnostic_ir": {
                                    "error_type": "model_check_error",
                                    "error_subtype": "compile_failure_unknown",
                                    "stage": "check",
                                    "observed_phase": "check",
                                },
                            },
                            {
                                "observed_failure_type": "none",
                                "diagnostic_ir": {
                                    "error_type": "none",
                                    "error_subtype": "none",
                                    "stage": "none",
                                    "observed_phase": "none",
                                },
                            },
                        ],
                    }
                ]
            },
            l3_quality_summary={
                "category_distribution": {"topology_wiring": 2},
                "subtype_distribution": {"compile_failure_unknown": 1},
            },
            l4_ab_compare_summary={},
            l5_summary={
                "gate_result": "PASS",
                "success_at_k_pct": 100.0,
                "failure_type_breakdown_on": {
                    "underconstrained_system": {"record_count": 1, "success_count": 1},
                },
                "category_breakdown_on": {
                    "topology_wiring": {"record_count": 1, "success_count": 1},
                },
            },
        )
        self.assertEqual(summary.get("status"), "PASS")
        by_failure_type = summary.get("by_failure_type") if isinstance(summary.get("by_failure_type"), dict) else {}
        under = by_failure_type.get("underconstrained_system") if isinstance(by_failure_type.get("underconstrained_system"), dict) else {}
        self.assertEqual(int(under.get("resolved_after_aligned_manifestation_count") or 0), 1)
        self.assertEqual(int(under.get("no_failure_signal_count") or 0), 0)
        outcome = summary.get("final_outcome_view") if isinstance(summary.get("final_outcome_view"), dict) else {}
        self.assertEqual(int(outcome.get("resolved_task_count") or 0), 1)

    def test_build_realism_summary_flags_missing_failure_signal_when_task_directly_resolves(self) -> None:
        summary = build_realism_summary_v1(
            evidence_summary={},
            challenge_summary={
                "counts_by_failure_type": {"underconstrained_system": 1},
                "counts_by_category": {"topology_wiring": 1},
            },
            challenge_manifest={},
            taskset_payload={
                "tasks": [
                    {
                        "task_id": "t_under",
                        "failure_type": "underconstrained_system",
                        "category": "topology_wiring",
                        "expected_stage": "check",
                    }
                ]
            },
            l3_run_results={
                "records": [
                    {
                        "task_id": "t_under",
                        "passed": True,
                        "attempts": [
                            {
                                "observed_failure_type": "none",
                                "diagnostic_ir": {
                                    "error_type": "none",
                                    "error_subtype": "none",
                                    "stage": "none",
                                    "observed_phase": "none",
                                },
                            }
                        ],
                    }
                ]
            },
            l3_quality_summary={
                "category_distribution": {"topology_wiring": 1},
                "subtype_distribution": {},
            },
            l4_ab_compare_summary={},
            l5_summary={
                "gate_result": "PASS",
                "success_at_k_pct": 100.0,
                "failure_type_breakdown_on": {
                    "underconstrained_system": {"record_count": 1, "success_count": 1},
                },
                "category_breakdown_on": {
                    "topology_wiring": {"record_count": 1, "success_count": 1},
                },
            },
        )
        self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
        self.assertEqual(summary.get("recommendation"), "repair_wave1_taxonomy_alignment")
        mismatch = summary.get("mismatch_summary") if isinstance(summary.get("mismatch_summary"), dict) else {}
        self.assertEqual(int(mismatch.get("missing_failure_signal_count") or 0), 1)
        by_failure_type = summary.get("by_failure_type") if isinstance(summary.get("by_failure_type"), dict) else {}
        under = by_failure_type.get("underconstrained_system") if isinstance(by_failure_type.get("underconstrained_system"), dict) else {}
        self.assertEqual(int(under.get("resolved_without_failure_signal_count") or 0), 1)

    def test_build_realism_summary_allows_initialization_direct_resolve_without_manifestation(self) -> None:
        summary = build_realism_summary_v1(
            evidence_summary={},
            challenge_summary={
                "counts_by_failure_type": {"initialization_infeasible": 1},
                "counts_by_category": {"initialization": 1},
            },
            challenge_manifest={},
            taskset_payload={
                "tasks": [
                    {
                        "task_id": "t_init",
                        "failure_type": "initialization_infeasible",
                        "category": "initialization",
                        "expected_stage": "simulate",
                    }
                ]
            },
            l3_run_results={
                "records": [
                    {
                        "task_id": "t_init",
                        "passed": True,
                        "attempts": [
                            {
                                "observed_failure_type": "none",
                                "diagnostic_ir": {
                                    "error_type": "none",
                                    "error_subtype": "none",
                                    "stage": "none",
                                    "observed_phase": "none",
                                },
                            }
                        ],
                    }
                ]
            },
            l3_quality_summary={
                "category_distribution": {"initialization": 1},
                "subtype_distribution": {},
            },
            l4_ab_compare_summary={},
            l5_summary={
                "gate_result": "PASS",
                "success_at_k_pct": 100.0,
                "failure_type_breakdown_on": {
                    "initialization_infeasible": {"record_count": 1, "success_count": 1},
                },
                "category_breakdown_on": {
                    "initialization": {"record_count": 1, "success_count": 1},
                },
            },
        )
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(summary.get("recommendation"), "ready_for_next_realism_iteration")
        mismatch = summary.get("mismatch_summary") if isinstance(summary.get("mismatch_summary"), dict) else {}
        self.assertEqual(int(mismatch.get("missing_failure_signal_count") or 0), 0)
        by_failure_type = summary.get("by_failure_type") if isinstance(summary.get("by_failure_type"), dict) else {}
        init_row = by_failure_type.get("initialization_infeasible") if isinstance(by_failure_type.get("initialization_infeasible"), dict) else {}
        self.assertEqual(int(init_row.get("resolved_without_failure_signal_count") or 0), 1)

    def test_build_realism_summary_counts_phase_drift_without_stage_mismatch(self) -> None:
        summary = build_realism_summary_v1(
            evidence_summary={},
            challenge_summary={
                "counts_by_failure_type": {"underconstrained_system": 1},
                "counts_by_category": {"topology_wiring": 1},
            },
            challenge_manifest={},
            taskset_payload={
                "tasks": [
                    {
                        "task_id": "t_under",
                        "failure_type": "underconstrained_system",
                        "category": "topology_wiring",
                        "expected_stage": "check",
                    }
                ]
            },
            l3_run_results={
                "records": [
                    {
                        "task_id": "t_under",
                        "attempts": [
                            {
                                "observed_failure_type": "model_check_error",
                                "diagnostic_ir": {
                                    "error_type": "model_check_error",
                                    "error_subtype": "underconstrained_system",
                                    "stage": "check",
                                    "observed_phase": "simulate",
                                },
                            }
                        ],
                    }
                ]
            },
            l3_quality_summary={
                "category_distribution": {"topology_wiring": 1},
                "subtype_distribution": {"underconstrained_system": 1},
                "observed_phase_distribution": {"simulate": 1},
                "phase_drift_count": 1,
            },
            l4_ab_compare_summary={},
            l5_summary={
                "gate_result": "PASS",
                "success_at_k_pct": 0.0,
                "failure_type_breakdown_on": {
                    "underconstrained_system": {"record_count": 1, "success_count": 0},
                },
                "category_breakdown_on": {
                    "topology_wiring": {"record_count": 1, "success_count": 0},
                },
            },
        )
        mismatch = summary.get("mismatch_summary") if isinstance(summary.get("mismatch_summary"), dict) else {}
        self.assertEqual(int(mismatch.get("stage_mismatch_count") or 0), 0)
        self.assertEqual(int(mismatch.get("phase_drift_count") or 0), 1)
        under = ((summary.get("by_failure_type") or {}).get("underconstrained_system") or {})
        self.assertEqual(float(under.get("stage_match_rate_pct") or 0.0), 100.0)
        self.assertEqual(int(under.get("phase_drift_count") or 0), 1)

    def test_build_realism_summary_uses_nested_executor_attempts_for_manifestation(self) -> None:
        summary = build_realism_summary_v1(
            evidence_summary={},
            challenge_summary={
                "counts_by_failure_type": {"underconstrained_system": 1},
                "counts_by_category": {"topology_wiring": 1},
            },
            challenge_manifest={},
            taskset_payload={
                "tasks": [
                    {
                        "task_id": "t_under",
                        "failure_type": "underconstrained_system",
                        "category": "topology_wiring",
                        "expected_stage": "check",
                    }
                ]
            },
            l3_run_results={
                "records": [
                    {
                        "task_id": "t_under",
                        "passed": True,
                        "attempts": [
                            {
                                "round": 1,
                                "check_model_pass": True,
                                "simulate_pass": True,
                                "executor_stdout_tail": json.dumps(
                                    {
                                        "task_id": "t_under",
                                        "executor_status": "PASS",
                                        "attempts": [
                                            {
                                                "round": 1,
                                                "observed_failure_type": "model_check_error",
                                                "diagnostic_ir": {
                                                    "error_type": "model_check_error",
                                                    "error_subtype": "underconstrained_system",
                                                    "stage": "check",
                                                    "observed_phase": "check",
                                                },
                                            }
                                        ],
                                    }
                                ),
                            }
                        ],
                    }
                ]
            },
            l3_quality_summary={
                "category_distribution": {"topology_wiring": 1},
                "subtype_distribution": {"underconstrained_system": 1},
            },
            l4_ab_compare_summary={},
            l5_summary={
                "gate_result": "PASS",
                "success_at_k_pct": 100.0,
                "failure_type_breakdown_on": {
                    "underconstrained_system": {"record_count": 1, "success_count": 1},
                },
                "category_breakdown_on": {
                    "topology_wiring": {"record_count": 1, "success_count": 1},
                },
            },
        )
        under = ((summary.get("by_failure_type") or {}).get("underconstrained_system") or {})
        mismatch = summary.get("mismatch_summary") if isinstance(summary.get("mismatch_summary"), dict) else {}
        self.assertEqual(int(under.get("manifestation_record_count") or 0), 1)
        self.assertEqual(float(under.get("canonical_match_rate_pct") or 0.0), 100.0)
        self.assertEqual(float(under.get("stage_match_rate_pct") or 0.0), 100.0)
        self.assertEqual(int(under.get("resolved_after_aligned_manifestation_count") or 0), 1)
        self.assertEqual(int(mismatch.get("missing_failure_signal_count") or 0), 0)

    def test_build_realism_summary_blocks_when_l3_l5_inputs_are_missing(self) -> None:
        summary = build_realism_summary_v1(
            evidence_summary={"acceptance_mode": "delta_uplift"},
            challenge_summary={
                "counts_by_failure_type": {"underconstrained_system": 1},
                "counts_by_category": {"topology_wiring": 1},
            },
            challenge_manifest={
                "baseline_provenance": {
                    "planner_backend": "gemini",
                    "llm_model": "gemini-3.1-pro-preview",
                }
            },
            taskset_payload={
                "tasks": [
                    {
                        "task_id": "t_under",
                        "failure_type": "underconstrained_system",
                        "category": "topology_wiring",
                        "expected_stage": "check",
                    }
                ]
            },
            l3_run_results={},
            l3_quality_summary={},
            l4_ab_compare_summary={},
            l5_summary={},
        )
        self.assertEqual(summary.get("status"), "BLOCKED")
        self.assertEqual(summary.get("recommendation"), "blocked_missing_realism_inputs")
        self.assertEqual((summary.get("failure_manifestation_view") or {}).get("status"), "BLOCKED")
        self.assertEqual((summary.get("final_outcome_view") or {}).get("status"), "BLOCKED")
        self.assertIn("l3_run_results_missing", summary.get("reasons") or [])
        self.assertIn("l5_summary_missing", summary.get("reasons") or [])


if __name__ == "__main__":
    unittest.main()
