import unittest

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
                                },
                            },
                            {
                                "observed_failure_type": "none",
                                "diagnostic_ir": {
                                    "error_type": "none",
                                    "error_subtype": "none",
                                    "stage": "none",
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


if __name__ == "__main__":
    unittest.main()
