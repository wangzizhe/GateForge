import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_realism_repair_queue_v1 import build_repair_queue_v1


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _taskset_payload() -> dict:
    return {
        "schema_version": "agent_modelica_taskset_v1",
        "tasks": [
            {
                "task_id": "t_connector",
                "origin_task_id": "origin_connector",
                "failure_type": "connector_mismatch",
                "category": "topology_wiring",
                "expected_stage": "check",
                "mutation_operator": "connector_port_typo",
                "mutation_operator_family": "topology_realism",
                "source_model_path": "/tmp/source_connector.mo",
                "mutated_model_path": "/tmp/mutated_connector.mo",
                "mutated_objects": [{"kind": "connection_endpoint"}],
            },
            {
                "task_id": "t_init",
                "origin_task_id": "origin_init",
                "failure_type": "initialization_infeasible",
                "category": "initialization",
                "expected_stage": "simulate",
                "mutation_operator": "initial_equation_assert",
                "mutation_operator_family": "initialization_realism",
                "source_model_path": "/tmp/source_init.mo",
                "mutated_model_path": "/tmp/mutated_init.mo",
                "mutated_objects": [{"kind": "initialization_trigger"}],
            },
            {
                "task_id": "t_under",
                "origin_task_id": "origin_under",
                "failure_type": "underconstrained_system",
                "category": "topology_wiring",
                "expected_stage": "check",
                "mutation_operator": "drop_connect_equation",
                "mutation_operator_family": "topology_realism",
                "source_model_path": "/tmp/source_under.mo",
                "mutated_model_path": "/tmp/mutated_under.mo",
                "mutated_objects": [{"kind": "connection_edge"}],
            },
        ],
    }


def _run_results_payload() -> dict:
    def _record(task_id: str, failure_type: str, subtype: str, stage: str, observed_failure_type: str) -> dict:
        return {
            "task_id": task_id,
            "failure_type": failure_type,
            "attempts": [
                {
                    "round": 1,
                    "observed_failure_type": observed_failure_type,
                    "diagnostic_ir": {
                        "error_type": observed_failure_type,
                        "error_subtype": subtype,
                        "stage": stage,
                    },
                }
            ],
        }

    return {
        "records": [
            _record("t_connector", "connector_mismatch", "compile_failure_unknown", "check", "model_check_error"),
            _record("t_init", "initialization_infeasible", "compile_failure_unknown", "check", "model_check_error"),
            _record("t_under", "underconstrained_system", "compile_failure_unknown", "check", "model_check_error"),
        ]
    }


def _diagnostic_quality_payload() -> dict:
    return {
        "schema_version": "agent_modelica_diagnostic_quality_v0",
        "status": "PASS",
        "total_attempts": 3,
        "parsed_attempts": 3,
        "parse_coverage_pct": 100.0,
        "type_match_rate_pct": 100.0,
        "stage_match_rate_pct": 100.0,
        "subtype_distribution": {"compile_failure_unknown": 3},
        "category_distribution": {
            "initialization": 1,
            "topology_wiring": 2,
        },
    }


def _realism_summary_payload() -> dict:
    return {
        "schema_version": "agent_modelica_realism_summary_v1",
        "status": "NEEDS_REVIEW",
        "recommendation": "repair_wave1_mutations",
        "taxonomy_view_mode": "dual_view",
        "mismatch_summary": {
            "canonical_type_mismatch_count": 1,
            "stage_mismatch_count": 1,
            "subtype_mismatch_count": 2,
            "missing_failure_signal_count": 0,
            "initialization_truncated_by_check_count": 1,
            "connector_subtype_match_rate_pct": 0.0,
            "initialization_simulate_stage_rate_pct": 0.0,
            "category_record_gap_count": 0,
            "missing_failure_type_records": [],
            "missing_categories": [],
        },
        "by_failure_type": {
            "connector_mismatch": {
                "task_count": 1,
                "l3_record_count": 1,
                "manifestation_record_count": 1,
                "canonical_match_rate_pct": 100.0,
                "stage_match_rate_pct": 100.0,
                "subtype_match_rate_pct": 0.0,
                "no_failure_signal_count": 0,
                "l5_success_count_on": 0,
            },
            "initialization_infeasible": {
                "task_count": 1,
                "l3_record_count": 1,
                "manifestation_record_count": 1,
                "canonical_match_rate_pct": 0.0,
                "stage_match_rate_pct": 0.0,
                "subtype_match_rate_pct": 0.0,
                "no_failure_signal_count": 0,
                "l5_success_count_on": 0,
            },
            "underconstrained_system": {
                "task_count": 1,
                "l3_record_count": 1,
                "manifestation_record_count": 1,
                "canonical_match_rate_pct": 100.0,
                "stage_match_rate_pct": 100.0,
                "subtype_match_rate_pct": 100.0,
                "no_failure_signal_count": 0,
                "l5_success_count_on": 0,
            },
        },
        "failure_manifestation_view": {
            "status": "NEEDS_REVIEW",
            "by_failure_type": {
                "connector_mismatch": {
                    "task_count": 1,
                    "l3_record_count": 1,
                    "manifestation_record_count": 1,
                    "canonical_match_rate_pct": 100.0,
                    "stage_match_rate_pct": 100.0,
                    "subtype_match_rate_pct": 0.0,
                    "no_failure_signal_count": 0,
                    "l5_success_count_on": 0,
                },
                "initialization_infeasible": {
                    "task_count": 1,
                    "l3_record_count": 1,
                    "manifestation_record_count": 1,
                    "canonical_match_rate_pct": 0.0,
                    "stage_match_rate_pct": 0.0,
                    "subtype_match_rate_pct": 0.0,
                    "no_failure_signal_count": 0,
                    "l5_success_count_on": 0,
                },
                "underconstrained_system": {
                    "task_count": 1,
                    "l3_record_count": 1,
                    "manifestation_record_count": 1,
                    "canonical_match_rate_pct": 100.0,
                    "stage_match_rate_pct": 100.0,
                    "subtype_match_rate_pct": 100.0,
                    "no_failure_signal_count": 0,
                    "l5_success_count_on": 0,
                },
            },
            "mismatch_summary": {
                "canonical_type_mismatch_count": 1,
                "stage_mismatch_count": 1,
                "subtype_mismatch_count": 2,
                "missing_failure_signal_count": 0,
                "initialization_truncated_by_check_count": 1,
                "connector_subtype_match_rate_pct": 0.0,
                "initialization_simulate_stage_rate_pct": 0.0,
                "category_record_gap_count": 0,
                "missing_failure_type_records": [],
                "missing_categories": [],
            },
        },
    }


def _signal_gap_run_results_payload() -> dict:
    return {
        "records": [
            {
                "task_id": "t_under",
                "failure_type": "underconstrained_system",
                "passed": True,
                "attempts": [
                    {
                        "round": 1,
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
    }


def _signal_gap_realism_summary_payload() -> dict:
    payload = {
        "schema_version": "agent_modelica_realism_summary_v1",
        "status": "NEEDS_REVIEW",
        "recommendation": "repair_wave1_taxonomy_alignment",
        "taxonomy_view_mode": "dual_view",
        "mismatch_summary": {
            "canonical_type_mismatch_count": 0,
            "stage_mismatch_count": 0,
            "subtype_mismatch_count": 0,
            "missing_failure_signal_count": 1,
            "initialization_truncated_by_check_count": 0,
            "connector_subtype_match_rate_pct": 100.0,
            "initialization_simulate_stage_rate_pct": 100.0,
            "category_record_gap_count": 0,
            "missing_failure_type_records": [],
            "missing_categories": [],
        },
        "by_failure_type": {
            "underconstrained_system": {
                "task_count": 1,
                "l3_record_count": 1,
                "manifestation_record_count": 0,
                "canonical_match_rate_pct": 0.0,
                "stage_match_rate_pct": 0.0,
                "subtype_match_rate_pct": 0.0,
                "no_failure_signal_count": 1,
                "l5_success_count_on": 1,
            }
        },
    }
    payload["failure_manifestation_view"] = {
        "status": "NEEDS_REVIEW",
        "by_failure_type": payload["by_failure_type"],
        "mismatch_summary": payload["mismatch_summary"],
    }
    return payload


def _shifted_under_run_results_payload() -> dict:
    return {
        "records": [
            {
                "task_id": "t_under",
                "failure_type": "underconstrained_system",
                "passed": False,
                "attempts": [
                    {
                        "round": 1,
                        "observed_failure_type": "simulate_error",
                        "diagnostic_ir": {
                            "error_type": "simulate_error",
                            "error_subtype": "simulation_failure_unknown",
                            "stage": "simulate",
                        },
                    }
                ],
            }
        ]
    }


def _shifted_under_realism_summary_payload() -> dict:
    payload = {
        "schema_version": "agent_modelica_realism_summary_v1",
        "status": "NEEDS_REVIEW",
        "recommendation": "repair_wave1_taxonomy_alignment",
        "taxonomy_view_mode": "dual_view",
        "mismatch_summary": {
            "canonical_type_mismatch_count": 1,
            "stage_mismatch_count": 1,
            "subtype_mismatch_count": 0,
            "missing_failure_signal_count": 0,
            "initialization_truncated_by_check_count": 0,
            "connector_subtype_match_rate_pct": 100.0,
            "initialization_simulate_stage_rate_pct": 100.0,
            "category_record_gap_count": 0,
            "missing_failure_type_records": [],
            "missing_categories": [],
        },
        "by_failure_type": {
            "underconstrained_system": {
                "task_count": 1,
                "l3_record_count": 1,
                "manifestation_record_count": 1,
                "canonical_match_rate_pct": 0.0,
                "stage_match_rate_pct": 0.0,
                "subtype_match_rate_pct": 0.0,
                "no_failure_signal_count": 0,
                "l5_success_count_on": 0,
            }
        },
    }
    payload["failure_manifestation_view"] = {
        "status": "NEEDS_REVIEW",
        "by_failure_type": payload["by_failure_type"],
        "mismatch_summary": payload["mismatch_summary"],
    }
    return payload


def _final_summary_payload(run_root: Path) -> dict:
    return {
        "schema_version": "agent_modelica_realism_final_run_summary_v1",
        "run_id": run_root.name,
        "run_root": str(run_root),
        "status": "NEEDS_REVIEW",
        "decision": "hold",
        "primary_reason": "taxonomy_alignment_failed",
        "acceptance_mode": "absolute_non_regression",
        "baseline_state": "baseline_saturated",
        "baseline_off_success_at_k_pct": 100.0,
        "taxonomy_alignment_status": "NEEDS_REVIEW",
        "taxonomy_alignment_recommendation": "repair_wave1_mutations",
        "paths": {
            "realism_internal_summary": str(run_root / "realism_internal_summary.json"),
        },
    }


def _build_finalized_run_fixture(run_root: Path, include_realism: bool = True) -> None:
    _write_json(run_root / "final_run_summary.json", _final_summary_payload(run_root))
    _write_json(run_root / "challenge" / "taskset_frozen.json", _taskset_payload())
    _write_json(run_root / "main_l5" / "l3" / "run2" / "run_results.json", _run_results_payload())
    _write_json(run_root / "main_l5" / "l3" / "run2" / "diagnostic_quality_summary.json", _diagnostic_quality_payload())
    if include_realism:
        _write_json(run_root / "realism_internal_summary.json", _realism_summary_payload())


class AgentModelicaRealismRepairQueueV1Tests(unittest.TestCase):
    def test_build_repair_queue_prioritizes_initialization_and_classifies_wave1_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            run_root = Path(d) / "run01"
            _build_finalized_run_fixture(run_root, include_realism=True)

            summary = build_repair_queue_v1(run_root=str(run_root), update_final_summary=True)
            tasks_payload = json.loads((run_root / "repair_queue_tasks.json").read_text(encoding="utf-8"))
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("top_priority_reason"), "stage_truncation")
            self.assertEqual(summary.get("top_repair_priority"), "initialization_infeasible:stage_truncation")
            priorities = summary.get("priorities") if isinstance(summary.get("priorities"), list) else []
            self.assertEqual(priorities[0].get("failure_type"), "initialization_infeasible")
            by_failure_type = summary.get("by_failure_type") if isinstance(summary.get("by_failure_type"), dict) else {}
            self.assertEqual((by_failure_type.get("connector_mismatch") or {}).get("priority_reason"), "subtype_signal_gap")
            self.assertEqual((by_failure_type.get("underconstrained_system") or {}).get("priority_reason"), "repair_policy_gap")
            self.assertEqual(sum(int((row or {}).get("affected_task_count") or 0) for row in by_failure_type.values()), 3)
            self.assertEqual(len(tasks_payload.get("tasks") or []), 3)
            self.assertEqual(final_summary.get("repair_queue_status"), "PASS")
            self.assertEqual(final_summary.get("top_repair_priority"), "initialization_infeasible:stage_truncation")

    def test_build_repair_queue_blocks_when_realism_summary_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            run_root = Path(d) / "run02"
            _build_finalized_run_fixture(run_root, include_realism=False)

            summary = build_repair_queue_v1(run_root=str(run_root), update_final_summary=True)
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(summary.get("status"), "BLOCKED")
            self.assertIn("realism_summary_missing", summary.get("reasons") or [])
            self.assertEqual(summary.get("task_queue_count"), 0)
            self.assertEqual(final_summary.get("repair_queue_status"), "BLOCKED")

    def test_build_repair_queue_uses_manifestation_signal_gap_for_structurally_silent_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            run_root = Path(d) / "run03"
            _write_json(run_root / "final_run_summary.json", _final_summary_payload(run_root))
            _write_json(run_root / "challenge" / "taskset_frozen.json", {"tasks": [_taskset_payload()["tasks"][-1]]})
            _write_json(run_root / "main_l5" / "l3" / "run2" / "run_results.json", _signal_gap_run_results_payload())
            _write_json(run_root / "main_l5" / "l3" / "run2" / "diagnostic_quality_summary.json", _diagnostic_quality_payload())
            _write_json(run_root / "realism_internal_summary.json", _signal_gap_realism_summary_payload())

            summary = build_repair_queue_v1(run_root=str(run_root), update_final_summary=True)

            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("top_repair_priority"), "underconstrained_system:manifestation_signal_gap")
            by_failure_type = summary.get("by_failure_type") if isinstance(summary.get("by_failure_type"), dict) else {}
            self.assertEqual((by_failure_type.get("underconstrained_system") or {}).get("priority_reason"), "manifestation_signal_gap")

    def test_build_repair_queue_classifies_underconstrained_stage_shift_as_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            run_root = Path(d) / "run04"
            _write_json(run_root / "final_run_summary.json", _final_summary_payload(run_root))
            _write_json(run_root / "challenge" / "taskset_frozen.json", {"tasks": [_taskset_payload()["tasks"][-1]]})
            _write_json(run_root / "main_l5" / "l3" / "run2" / "run_results.json", _shifted_under_run_results_payload())
            _write_json(run_root / "main_l5" / "l3" / "run2" / "diagnostic_quality_summary.json", _diagnostic_quality_payload())
            _write_json(run_root / "realism_internal_summary.json", _shifted_under_realism_summary_payload())

            summary = build_repair_queue_v1(run_root=str(run_root), update_final_summary=True)

            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("top_repair_priority"), "underconstrained_system:manifestation_stage_shift")
            by_failure_type = summary.get("by_failure_type") if isinstance(summary.get("by_failure_type"), dict) else {}
            self.assertEqual((by_failure_type.get("underconstrained_system") or {}).get("priority_reason"), "manifestation_stage_shift")

    def test_finalize_run_updates_final_summary_with_repair_queue_fields(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_dir = root / "out"
            run_root = out_dir / "runs" / "queue01"
            subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.agent_modelica_realism_run_lifecycle_v1",
                    "init-run",
                    "--out-dir",
                    str(out_dir),
                    "--run-root",
                    str(run_root),
                    "--run-id",
                    "queue01",
                    "--pack-id",
                    "agent_modelica_realism_pack_v1",
                    "--pack-version",
                    "v1",
                    "--pack-track",
                    "realism",
                    "--acceptance-scope",
                    "independent_validation",
                    "--base-taskset",
                    str(run_root / "challenge" / "taskset_frozen.json"),
                    "--lock-path",
                    str(out_dir / ".lock.json"),
                    "--update-latest",
                    "1",
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            _write_json(
                run_root / "summary.json",
                {
                    "schema_version": "agent_modelica_l4_uplift_evidence_bundle_v0",
                    "status": "PASS",
                    "decision": "hold",
                    "primary_reason": "taxonomy_alignment_failed",
                    "acceptance_mode": "absolute_non_regression",
                    "main_success_at_k_pct": 0.0,
                },
            )
            _write_json(
                run_root / "challenge" / "frozen_summary.json",
                {
                    "schema_version": "agent_modelica_l4_challenge_frozen_summary_v0",
                    "status": "PASS",
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                    "baseline_off_success_at_k_pct": 100.0,
                    "baseline_has_headroom": False,
                },
            )
            _write_json(
                run_root / "main_l5" / "l5_eval_summary.json",
                {
                    "status": "FAIL",
                    "gate_result": "FAIL",
                    "success_at_k_pct": 0.0,
                    "failure_type_breakdown_on": {},
                    "category_breakdown_on": {},
                },
            )
            _write_json(run_root / "challenge" / "taskset_frozen.json", _taskset_payload())
            _write_json(run_root / "main_l5" / "l3" / "run2" / "run_results.json", _run_results_payload())
            _write_json(run_root / "main_l5" / "l3" / "run2" / "diagnostic_quality_summary.json", _diagnostic_quality_payload())
            _write_json(run_root / "realism_internal_summary.json", _realism_summary_payload())

            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.agent_modelica_realism_run_lifecycle_v1",
                    "finalize-run",
                    "--out-dir",
                    str(out_dir),
                    "--run-root",
                    str(run_root),
                    "--update-latest",
                    "1",
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(final_summary.get("repair_queue_status"), "PASS")
            self.assertEqual(final_summary.get("top_repair_priority"), "initialization_infeasible:stage_truncation")
            self.assertEqual(Path(final_summary.get("repair_queue_path") or "").name, "repair_queue_summary.json")


if __name__ == "__main__":
    unittest.main()
