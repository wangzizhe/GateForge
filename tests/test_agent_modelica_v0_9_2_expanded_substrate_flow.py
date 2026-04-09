from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_9_2_closeout import build_v092_closeout
from gateforge.agent_modelica_v0_9_2_expanded_substrate_admission import build_v092_expanded_substrate_admission
from gateforge.agent_modelica_v0_9_2_expanded_substrate_builder import build_v092_expanded_substrate_builder
from gateforge.agent_modelica_v0_9_2_handoff_integrity import build_v092_handoff_integrity


def _candidate(task_id: str, source_id: str, barrier: str, family: str, complexity: str, template: str) -> dict:
    return {
        "task_id": task_id,
        "base_task_id": task_id,
        "source_id": source_id,
        "family_id": family,
        "workflow_task_template_id": template,
        "complexity_tier": complexity,
        "goal_specific_check_mode": "artifact_only" if barrier else "invariant_only",
        "authenticity_audit": {
            "source_provenance": source_id,
            "workflow_proximity_pass": True,
            "anti_fake_workflow_pass": True,
            "context_naturalness_risk": "low" if source_id.startswith("v080") else "medium",
            "goal_level_acceptance_is_realistic": True,
            "authenticity_audit_pass": True,
        },
        "barrier_sampling_audit": {
            "barrier_sampling_intent_present": bool(barrier),
            "target_barrier_family": barrier,
            "barrier_sampling_rationale": "fixture",
            "selection_priority_reason": "fixture",
            "task_definition_was_changed_for_barrier_targeting": False,
            "barrier_sampling_audit_pass": True,
        },
    }


def _write_v091_closeout(path: Path, *, version_decision: str = "v0_9_1_real_candidate_source_expansion_ready") -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "candidate_source_expansion_status": "ready",
            "post_expansion_candidate_pool_count": 28,
            "candidate_depth_by_priority_barrier": {
                "goal_artifact_missing_after_surface_fix": 8,
                "dispatch_or_policy_limited_unresolved": 8,
                "workflow_spillover_unresolved": 8,
            },
            "v0_9_2_handoff_mode": "freeze_first_expanded_authentic_workflow_substrate",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_pool_delta_ready(path: Path) -> None:
    rows = [
        _candidate("v080_case_01", "v080_real_frozen_workflow_proximal_substrate", "", "component_api_alignment", "complex", "restore_nominal_supply_chain"),
        _candidate("v080_case_02", "v080_real_frozen_workflow_proximal_substrate", "", "component_api_alignment", "complex", "recover_reporting_chain"),
        _candidate("v080_case_03", "v080_real_frozen_workflow_proximal_substrate", "", "local_interface_alignment", "medium", "restore_boundary_signal_integrity"),
        _candidate("v080_case_04", "v080_real_frozen_workflow_proximal_substrate", "", "local_interface_alignment", "medium", "restore_boundary_signal_integrity"),
        _candidate("v080_case_05", "v080_real_frozen_workflow_proximal_substrate", "goal_artifact_missing_after_surface_fix", "medium_redeclare_alignment", "medium", "recover_medium_goal"),
        _candidate("v080_case_06", "v080_real_frozen_workflow_proximal_substrate", "goal_artifact_missing_after_surface_fix", "medium_redeclare_alignment", "simple", "recover_medium_goal"),
        _candidate("v080_case_07", "v080_real_frozen_workflow_proximal_substrate", "dispatch_or_policy_limited_unresolved", "component_api_alignment", "complex", "restore_nominal_supply_chain"),
        _candidate("v080_case_08", "v080_real_frozen_workflow_proximal_substrate", "workflow_spillover_unresolved", "component_api_alignment", "complex", "recover_reporting_chain"),
        _candidate("v080_case_09", "v080_real_frozen_workflow_proximal_substrate", "dispatch_or_policy_limited_unresolved", "local_interface_alignment", "medium", "restore_boundary_signal_integrity"),
        _candidate("v080_case_10", "v080_real_frozen_workflow_proximal_substrate", "workflow_spillover_unresolved", "medium_redeclare_alignment", "simple", "recover_medium_goal"),
    ]
    for i in range(6):
        rows.append(_candidate(f"u_goal_{i}", "l4_uplift_challenge_frozen", "goal_artifact_missing_after_surface_fix", "medium_redeclare_alignment", "medium", "recover_medium_goal"))
        rows.append(_candidate(f"u_dispatch_{i}", "l4_uplift_challenge_frozen", "dispatch_or_policy_limited_unresolved", "component_api_alignment" if i % 2 == 0 else "local_interface_alignment", "medium", "restore_nominal_supply_chain" if i % 2 == 0 else "restore_boundary_signal_integrity"))
        rows.append(_candidate(f"u_spill_{i}", "l4_uplift_challenge_frozen", "workflow_spillover_unresolved", "component_api_alignment" if i % 2 == 0 else "medium_redeclare_alignment", "small", "recover_reporting_chain"))
    payload = {"post_expansion_candidate_pool": rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV092ExpandedSubstrateFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v091_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v091 = root / "v091" / "summary.json"
            _write_v091_closeout(v091)
            payload = build_v092_handoff_integrity(v091_closeout_path=str(v091), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_builder_freezes_ready_substrate_with_deterministic_baseline_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pool = root / "pool" / "summary.json"
            _write_pool_delta_ready(pool)
            payload = build_v092_expanded_substrate_builder(v091_pool_delta_path=str(pool), out_dir=str(root / "builder"))
            self.assertEqual(payload["expanded_substrate_candidate_count"], 19)
            self.assertEqual(payload["baseline_rows_preserved_count"], 10)
            self.assertEqual(
                payload["priority_barrier_coverage_table"],
                {
                    "goal_artifact_missing_after_surface_fix": 5,
                    "dispatch_or_policy_limited_unresolved": 5,
                    "workflow_spillover_unresolved": 5,
                },
            )

    def test_closeout_routes_to_partial_when_valid_substrate_remains_below_ready_floors(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v091 = root / "v091" / "summary.json"
            _write_v091_closeout(v091)
            builder_payload = {
                "expanded_substrate_candidate_table": [
                    _candidate("a1", "v080_real_frozen_workflow_proximal_substrate", "goal_artifact_missing_after_surface_fix", "medium_redeclare_alignment", "medium", "recover_medium_goal"),
                    _candidate("a2", "v080_real_frozen_workflow_proximal_substrate", "dispatch_or_policy_limited_unresolved", "component_api_alignment", "complex", "restore_nominal_supply_chain"),
                    _candidate("a3", "v080_real_frozen_workflow_proximal_substrate", "workflow_spillover_unresolved", "component_api_alignment", "complex", "recover_reporting_chain"),
                    _candidate("a4", "l4_uplift_challenge_frozen", "goal_artifact_missing_after_surface_fix", "medium_redeclare_alignment", "medium", "recover_medium_goal"),
                    _candidate("a5", "l4_uplift_challenge_frozen", "dispatch_or_policy_limited_unresolved", "local_interface_alignment", "medium", "restore_boundary_signal_integrity"),
                    _candidate("a6", "l4_uplift_challenge_frozen", "workflow_spillover_unresolved", "medium_redeclare_alignment", "small", "recover_reporting_chain"),
                ],
                "workflow_family_mix": {
                    "component_api_alignment": 2,
                    "local_interface_alignment": 1,
                    "medium_redeclare_alignment": 3,
                },
                "complexity_mix": {"complex": 2, "medium": 3, "small": 1},
                "goal_specific_check_mode_mix": {"artifact_only": 4, "invariant_only": 2},
                "workflow_task_template_mix": {
                    "recover_medium_goal": 2,
                    "recover_reporting_chain": 2,
                    "restore_nominal_supply_chain": 1,
                    "restore_boundary_signal_integrity": 1,
                },
                "priority_barrier_coverage_table": {
                    "goal_artifact_missing_after_surface_fix": 2,
                    "dispatch_or_policy_limited_unresolved": 2,
                    "workflow_spillover_unresolved": 2,
                },
            }
            builder_path = root / "builder" / "summary.json"
            builder_path.parent.mkdir(parents=True, exist_ok=True)
            builder_path.write_text(json.dumps(builder_payload), encoding="utf-8")
            payload = build_v092_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                expanded_substrate_builder_path=str(builder_path),
                expanded_substrate_admission_path=str(root / "admission" / "summary.json"),
                v091_closeout_path=str(v091),
                v091_pool_delta_path=str(root / "unused_pool" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_2_first_expanded_authentic_workflow_substrate_partial")

    def test_closeout_returns_invalid_when_priority_barrier_collapses(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v091 = root / "v091" / "summary.json"
            _write_v091_closeout(v091)
            builder_payload = {
                "expanded_substrate_candidate_table": [
                    _candidate("a1", "v080_real_frozen_workflow_proximal_substrate", "goal_artifact_missing_after_surface_fix", "medium_redeclare_alignment", "medium", "recover_medium_goal"),
                    _candidate("a2", "v080_real_frozen_workflow_proximal_substrate", "dispatch_or_policy_limited_unresolved", "component_api_alignment", "complex", "restore_nominal_supply_chain"),
                ],
                "workflow_family_mix": {"component_api_alignment": 1, "medium_redeclare_alignment": 1},
                "complexity_mix": {"complex": 1, "medium": 1},
                "goal_specific_check_mode_mix": {"artifact_only": 1, "invariant_only": 1},
                "workflow_task_template_mix": {"recover_medium_goal": 1, "restore_nominal_supply_chain": 1},
                "priority_barrier_coverage_table": {
                    "goal_artifact_missing_after_surface_fix": 1,
                    "dispatch_or_policy_limited_unresolved": 1,
                    "workflow_spillover_unresolved": 0,
                },
            }
            builder_path = root / "builder" / "summary.json"
            builder_path.parent.mkdir(parents=True, exist_ok=True)
            builder_path.write_text(json.dumps(builder_payload), encoding="utf-8")
            payload = build_v092_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                expanded_substrate_builder_path=str(builder_path),
                expanded_substrate_admission_path=str(root / "admission" / "summary.json"),
                v091_closeout_path=str(v091),
                v091_pool_delta_path=str(root / "unused_pool" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_2_expanded_substrate_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
