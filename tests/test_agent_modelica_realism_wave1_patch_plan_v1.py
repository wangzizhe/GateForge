import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_realism_repair_queue_v1 import build_repair_queue_v1
from gateforge.agent_modelica_realism_wave1_patch_plan_v1 import build_wave1_patch_plan_v1


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
    def _record(task_id: str, subtype: str, stage: str, observed_failure_type: str) -> dict:
        return {
            "task_id": task_id,
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
            _record("t_connector", "compile_failure_unknown", "check", "model_check_error"),
            _record("t_init", "compile_failure_unknown", "check", "model_check_error"),
            _record("t_under", "compile_failure_unknown", "check", "model_check_error"),
        ]
    }


def _refreshed_run_results_payload() -> dict:
    def _record(task_id: str, subtype: str, stage: str, observed_failure_type: str) -> dict:
        return {
            "task_id": task_id,
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
            _record("t_connector", "connector_mismatch", "check", "model_check_error"),
            _record("t_init", "init_failure", "simulate", "simulate_error"),
            _record("t_under", "compile_failure_unknown", "check", "model_check_error"),
        ]
    }


def _diagnostic_quality_payload() -> dict:
    return {
        "schema_version": "agent_modelica_diagnostic_quality_v0",
        "status": "PASS",
        "subtype_distribution": {"compile_failure_unknown": 3},
        "category_distribution": {"initialization": 1, "topology_wiring": 2},
    }


def _realism_summary_payload() -> dict:
    payload = {
        "schema_version": "agent_modelica_realism_summary_v1",
        "status": "NEEDS_REVIEW",
        "recommendation": "repair_wave1_mutations",
        "taxonomy_view_mode": "dual_view",
        "mismatch_summary": {
            "missing_failure_signal_count": 0,
            "initialization_truncated_by_check_count": 1,
            "connector_subtype_match_rate_pct": 0.0,
            "initialization_simulate_stage_rate_pct": 0.0,
        },
        "by_failure_type": {
            "connector_mismatch": {
                "manifestation_record_count": 1,
                "canonical_match_rate_pct": 100.0,
                "stage_match_rate_pct": 100.0,
                "no_failure_signal_count": 0,
                "l5_success_count_on": 0,
            },
            "initialization_infeasible": {
                "manifestation_record_count": 1,
                "canonical_match_rate_pct": 0.0,
                "stage_match_rate_pct": 0.0,
                "no_failure_signal_count": 0,
                "l5_success_count_on": 0,
            },
            "underconstrained_system": {
                "manifestation_record_count": 1,
                "canonical_match_rate_pct": 100.0,
                "stage_match_rate_pct": 100.0,
                "no_failure_signal_count": 0,
                "l5_success_count_on": 0,
            },
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
        "taxonomy_alignment_status": "NEEDS_REVIEW",
        "taxonomy_alignment_recommendation": "repair_wave1_mutations",
        "paths": {},
    }


def _build_finalized_run_fixture(run_root: Path, include_queue: bool = True) -> None:
    _write_json(run_root / "final_run_summary.json", _final_summary_payload(run_root))
    _write_json(run_root / "challenge" / "taskset_frozen.json", _taskset_payload())
    _write_json(run_root / "main_l5" / "l3" / "run2" / "run_results.json", _run_results_payload())
    _write_json(run_root / "main_l5" / "l3" / "run2" / "diagnostic_quality_summary.json", _diagnostic_quality_payload())
    _write_json(run_root / "realism_internal_summary.json", _realism_summary_payload())
    if include_queue:
        build_repair_queue_v1(run_root=str(run_root), update_final_summary=True)


def _build_signal_gap_fixture(run_root: Path) -> None:
    _write_json(run_root / "final_run_summary.json", _final_summary_payload(run_root))
    _write_json(run_root / "challenge" / "taskset_frozen.json", {"tasks": [_taskset_payload()["tasks"][-1]]})
    _write_json(
        run_root / "main_l5" / "l3" / "run2" / "run_results.json",
        {
            "records": [
                {
                    "task_id": "t_under",
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
        },
    )
    _write_json(run_root / "main_l5" / "l3" / "run2" / "diagnostic_quality_summary.json", _diagnostic_quality_payload())
    _write_json(
        run_root / "realism_internal_summary.json",
        {
            "schema_version": "agent_modelica_realism_summary_v1",
            "status": "NEEDS_REVIEW",
            "recommendation": "repair_wave1_taxonomy_alignment",
            "taxonomy_view_mode": "dual_view",
            "mismatch_summary": {
                "missing_failure_signal_count": 1,
                "initialization_truncated_by_check_count": 0,
                "connector_subtype_match_rate_pct": 100.0,
                "initialization_simulate_stage_rate_pct": 100.0,
            },
            "by_failure_type": {
                "underconstrained_system": {
                    "manifestation_record_count": 0,
                    "canonical_match_rate_pct": 0.0,
                    "stage_match_rate_pct": 0.0,
                    "no_failure_signal_count": 1,
                    "l5_success_count_on": 1,
                }
            },
            "failure_manifestation_view": {
                "status": "NEEDS_REVIEW",
                "by_failure_type": {
                    "underconstrained_system": {
                        "manifestation_record_count": 0,
                        "canonical_match_rate_pct": 0.0,
                        "stage_match_rate_pct": 0.0,
                        "no_failure_signal_count": 1,
                        "l5_success_count_on": 1,
                    }
                },
                "mismatch_summary": {
                    "missing_failure_signal_count": 1,
                    "initialization_truncated_by_check_count": 0,
                    "connector_subtype_match_rate_pct": 100.0,
                    "initialization_simulate_stage_rate_pct": 100.0,
                },
            },
        },
    )
    build_repair_queue_v1(run_root=str(run_root), update_final_summary=True)


class AgentModelicaRealismWave1PatchPlanV1Tests(unittest.TestCase):
    def test_build_patch_plan_outputs_operator_and_playbook_changes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            run_root = Path(d) / "run01"
            _build_finalized_run_fixture(run_root, include_queue=True)

            summary = build_wave1_patch_plan_v1(run_root=str(run_root), update_final_summary=True)
            tasks_payload = json.loads((run_root / "wave1_patch_plan_tasks.json").read_text(encoding="utf-8"))
            playbook_payload = json.loads((run_root / "wave1_focused_playbook.json").read_text(encoding="utf-8"))
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("top_patch_target"), "initialization_realism:initial_equation_assert")
            self.assertEqual(int(summary.get("operator_change_count") or 0), 3)
            self.assertEqual(int(summary.get("playbook_update_count") or 0), 3)
            self.assertEqual(len(tasks_payload.get("tasks") or []), 3)
            self.assertEqual(playbook_payload.get("status"), "PASS")
            init_entry = [x for x in (playbook_payload.get("playbook") or []) if x.get("failure_type") == "initialization_infeasible"][0]
            self.assertEqual(init_entry.get("focus_tag"), "realism_wave1_patch_plan")
            self.assertEqual(final_summary.get("patch_plan_status"), "PASS")
            self.assertEqual(final_summary.get("top_patch_target"), "initialization_realism:initial_equation_assert")

    def test_build_patch_plan_blocks_when_repair_queue_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            run_root = Path(d) / "run02"
            _build_finalized_run_fixture(run_root, include_queue=False)

            summary = build_wave1_patch_plan_v1(run_root=str(run_root), update_final_summary=True)
            final_summary = json.loads((run_root / "final_run_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(summary.get("status"), "BLOCKED")
            self.assertIn("repair_queue_missing", summary.get("reasons") or [])
            self.assertEqual(final_summary.get("patch_plan_status"), "BLOCKED")

    def test_build_patch_plan_maps_underconstrained_signal_gap_to_operator_rework(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            run_root = Path(d) / "run03"
            _build_signal_gap_fixture(run_root)

            summary = build_wave1_patch_plan_v1(run_root=str(run_root), update_final_summary=True)

            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("top_patch_target"), "topology_realism:drop_connect_equation")
            operator_changes = summary.get("operator_changes") if isinstance(summary.get("operator_changes"), list) else []
            self.assertEqual((operator_changes[0] or {}).get("patch_kind"), "operator_rework")

    def test_finalize_run_updates_final_summary_with_patch_plan_fields(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_dir = root / "out"
            run_root = out_dir / "runs" / "patch01"
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
                    "patch01",
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
                    "baseline_off_success_at_k_pct": 100.0,
                    "pack_id": "agent_modelica_realism_pack_v1",
                    "pack_version": "v1",
                    "pack_track": "realism",
                    "acceptance_scope": "independent_validation",
                },
            )
            _build_finalized_run_fixture(run_root, include_queue=True)
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
            report = subprocess.run(
                [
                    "python3",
                    "-m",
                    "gateforge.agent_modelica_realism_run_lifecycle_v1",
                    "report",
                    "--out-dir",
                    str(out_dir),
                    "--run-root",
                    str(run_root),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            payload = json.loads(report.stdout)
            self.assertEqual(final_summary.get("patch_plan_status"), "PASS")
            self.assertEqual(final_summary.get("top_patch_target"), "initialization_realism:initial_equation_assert")
            self.assertEqual(payload.get("patch_plan_status"), "PASS")
            self.assertEqual(payload.get("top_patch_target"), "initialization_realism:initial_equation_assert")

    def test_finalize_run_refreshes_stale_realism_summary_before_repair_queue(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_dir = root / "out"
            run_root = out_dir / "runs" / "refresh01"
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
                    "refresh01",
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
                    "baseline_off_success_at_k_pct": 100.0,
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
            )
            _write_json(run_root / "challenge" / "manifest.json", {"baseline_provenance": {"planner_backend": "gemini"}})
            _write_json(run_root / "challenge" / "taskset_frozen.json", _taskset_payload())
            _write_json(run_root / "main_l5" / "l3" / "run2" / "run_results.json", _refreshed_run_results_payload())
            _write_json(run_root / "main_l5" / "l3" / "run2" / "diagnostic_quality_summary.json", _diagnostic_quality_payload())
            _write_json(
                run_root / "main_l5" / "l5_eval_summary.json",
                {
                    "status": "PASS",
                    "gate_result": "PASS",
                    "success_at_k_pct": 33.33,
                    "failure_type_breakdown_on": {
                        "underconstrained_system": {"record_count": 1},
                        "connector_mismatch": {"record_count": 1},
                        "initialization_infeasible": {"record_count": 1},
                    },
                    "category_breakdown_on": {
                        "topology_wiring": {"record_count": 2},
                        "initialization": {"record_count": 1},
                    },
                },
            )
            _write_json(
                run_root / "realism_internal_summary.json",
                {
                    "schema_version": "agent_modelica_realism_summary_v1",
                    "status": "NEEDS_REVIEW",
                    "recommendation": "repair_wave1_mutations",
                    "mismatch_summary": {
                        "initialization_truncated_by_check_count": 1,
                        "connector_subtype_match_rate_pct": 0.0,
                        "initialization_simulate_stage_rate_pct": 0.0,
                    },
                    "by_failure_type": {
                        "connector_mismatch": {
                            "canonical_match_rate_pct": 100.0,
                            "stage_match_rate_pct": 100.0,
                            "l5_success_count_on": 0,
                        },
                        "initialization_infeasible": {
                            "canonical_match_rate_pct": 0.0,
                            "stage_match_rate_pct": 0.0,
                            "l5_success_count_on": 0,
                        },
                        "underconstrained_system": {
                            "canonical_match_rate_pct": 100.0,
                            "stage_match_rate_pct": 100.0,
                            "l5_success_count_on": 0,
                        },
                    },
                },
            )
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
            refreshed_realism = json.loads((run_root / "realism_internal_summary.json").read_text(encoding="utf-8"))
            refreshed_queue = json.loads((run_root / "repair_queue_summary.json").read_text(encoding="utf-8"))
            self.assertEqual((refreshed_realism.get("mismatch_summary") or {}).get("initialization_truncated_by_check_count"), 0)
            self.assertEqual(refreshed_queue.get("top_repair_priority"), "underconstrained_system:repair_policy_gap")


if __name__ == "__main__":
    unittest.main()
