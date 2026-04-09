from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_9_0_candidate_validator import evaluate_candidate_row
from gateforge.agent_modelica_v0_9_0_closeout import build_v090_closeout
from gateforge.agent_modelica_v0_9_0_depth_probe import build_v090_depth_probe
from gateforge.agent_modelica_v0_9_0_governance_pack import build_baseline_candidate_rows, build_v090_governance_pack
from gateforge.agent_modelica_v0_9_0_handoff_integrity import build_v090_handoff_integrity


def _write_v086_closeout(path: Path, *, version_decision: str = "v0_8_phase_nearly_complete_with_explicit_caveat") -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "v0_9_primary_phase_question": "authenticity_constrained_barrier_aware_workflow_expansion",
            "do_not_continue_v0_8_same_logic_refinement_by_default": True,
            "explicit_caveat_label": "workflow_readiness_remains_partial_rather_than_supported_on_frozen_workflow_proximal_substrate",
            "v0_9_handoff_mode": "start_next_phase_with_explicit_v0_8_caveat",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v080_closeout(path: Path) -> None:
    task_rows = [
        {
            "task_id": "v080_case_05",
            "base_task_id": "case_05",
            "family_id": "medium_redeclare_alignment",
            "workflow_task_template_id": "recover_medium_goal",
            "complexity_tier": "medium",
            "workflow_goal_present": True,
            "contextually_plausible": True,
            "non_trivial_from_context_alone": True,
            "workflow_proximity_audit_pass": True,
            "goal_specific_check_present": True,
            "workflow_acceptance_checks": [{"type": "expected_goal_artifact_present"}],
        },
        {
            "task_id": "v080_case_07",
            "base_task_id": "case_07",
            "family_id": "component_api_alignment",
            "workflow_task_template_id": "restore_nominal_supply_chain",
            "complexity_tier": "complex",
            "workflow_goal_present": True,
            "contextually_plausible": True,
            "non_trivial_from_context_alone": True,
            "workflow_proximity_audit_pass": True,
            "goal_specific_check_present": True,
            "workflow_acceptance_checks": [{"type": "named_result_invariant_pass"}],
        },
        {
            "task_id": "v080_case_08",
            "base_task_id": "case_08",
            "family_id": "component_api_alignment",
            "workflow_task_template_id": "recover_reporting_chain",
            "complexity_tier": "complex",
            "workflow_goal_present": True,
            "contextually_plausible": True,
            "non_trivial_from_context_alone": True,
            "workflow_proximity_audit_pass": True,
            "goal_specific_check_present": True,
            "workflow_acceptance_checks": [{"type": "expected_goal_artifact_present"}],
        },
    ]
    payload = {"workflow_proximal_substrate": {"task_rows": task_rows}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v081_closeout(path: Path) -> None:
    payload = {
        "workflow_profile_characterization": {
            "case_characterization_table": [
                {
                    "task_id": "v080_case_05",
                    "pilot_outcome": "surface_fix_only",
                    "primary_barrier_label": "goal_artifact_missing_after_surface_fix",
                },
                {
                    "task_id": "v080_case_07",
                    "pilot_outcome": "unresolved",
                    "primary_barrier_label": "dispatch_or_policy_limited_unresolved",
                },
                {
                    "task_id": "v080_case_08",
                    "pilot_outcome": "unresolved",
                    "primary_barrier_label": "workflow_spillover_unresolved",
                },
            ]
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV090CandidatePoolGovernanceFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v086_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v086 = root / "v086" / "summary.json"
            _write_v086_closeout(v086)
            payload = build_v090_handoff_integrity(v086_closeout_path=str(v086), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_candidate_with_high_context_naturalness_risk_is_rejected(self) -> None:
        candidate = {
            "task_id": "case",
            "source_id": "source",
            "family_id": "family",
            "workflow_task_template_id": "template",
            "complexity_tier": "medium",
            "authenticity_audit": {
                "source_provenance": "source",
                "workflow_proximity_pass": True,
                "anti_fake_workflow_pass": True,
                "context_naturalness_risk": "high",
                "goal_level_acceptance_is_realistic": True,
                "authenticity_audit_pass": False,
            },
            "barrier_sampling_audit": {
                "barrier_sampling_intent_present": False,
                "target_barrier_family": "",
                "barrier_sampling_rationale": "",
                "selection_priority_reason": "",
                "task_definition_was_changed_for_barrier_targeting": False,
                "barrier_sampling_audit_pass": True,
            },
        }
        result = evaluate_candidate_row(candidate)
        self.assertFalse(result["admitted"])
        self.assertIn("reject_high_context_naturalness_risk", result["rejection_reasons"])

    def test_candidate_with_medium_context_naturalness_risk_can_pass(self) -> None:
        candidate = {
            "task_id": "case",
            "source_id": "source",
            "family_id": "family",
            "workflow_task_template_id": "template",
            "complexity_tier": "medium",
            "authenticity_audit": {
                "source_provenance": "source",
                "workflow_proximity_pass": True,
                "anti_fake_workflow_pass": True,
                "context_naturalness_risk": "medium",
                "goal_level_acceptance_is_realistic": True,
                "authenticity_audit_pass": True,
            },
            "barrier_sampling_audit": {
                "barrier_sampling_intent_present": True,
                "target_barrier_family": "dispatch_or_policy_limited_unresolved",
                "barrier_sampling_rationale": "real candidate",
                "selection_priority_reason": "thin slice",
                "task_definition_was_changed_for_barrier_targeting": False,
                "barrier_sampling_audit_pass": True,
            },
        }
        result = evaluate_candidate_row(candidate)
        self.assertTrue(result["admitted"])

    def test_depth_probe_marks_current_thin_baseline_as_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v080 = root / "v080" / "summary.json"
            v081 = root / "v081" / "summary.json"
            _write_v080_closeout(v080)
            _write_v081_closeout(v081)
            governance = build_v090_governance_pack(
                v080_closeout_path=str(v080),
                v081_closeout_path=str(v081),
                out_dir=str(root / "governance"),
            )
            self.assertEqual(governance["candidate_pool_total_count"], 3)
            probe = build_v090_depth_probe(
                governance_pack_path=str(root / "governance" / "summary.json"),
                out_dir=str(root / "probe"),
            )
            self.assertEqual(probe["candidate_pool_governance_status"], "partial")
            self.assertTrue(probe["needs_additional_real_sources"])
            self.assertFalse(probe["degraded_floor_fully_met"])
            self.assertEqual(
                probe["candidate_depth_by_priority_barrier"],
                {
                    "goal_artifact_missing_after_surface_fix": 1,
                    "dispatch_or_policy_limited_unresolved": 1,
                    "workflow_spillover_unresolved": 1,
                },
            )

    def test_closeout_routes_to_partial_for_real_thin_pool(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v086 = root / "v086" / "summary.json"
            _write_v086_closeout(v086)
            payload = build_v090_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                depth_probe_path=str(root / "probe" / "summary.json"),
                v086_closeout_path=str(v086),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_0_candidate_pool_governance_partial")
            self.assertEqual(
                payload["conclusion"]["v0_9_1_handoff_mode"],
                "expand_real_candidate_pool_before_substrate_freeze",
            )
            self.assertTrue(payload["conclusion"]["needs_additional_real_sources"])

    def test_depth_probe_reports_single_count_per_barrier_as_partial_below_degraded_floor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            governance_path = root / "governance" / "summary.json"
            payload = {
                "baseline_candidate_rows": [
                    {
                        "task_id": "a",
                        "source_id": "source",
                        "family_id": "family",
                        "workflow_task_template_id": "template",
                        "complexity_tier": "medium",
                        "authenticity_audit": {
                            "source_provenance": "source",
                            "workflow_proximity_pass": True,
                            "anti_fake_workflow_pass": True,
                            "context_naturalness_risk": "low",
                            "goal_level_acceptance_is_realistic": True,
                            "authenticity_audit_pass": True,
                        },
                        "barrier_sampling_audit": {
                            "barrier_sampling_intent_present": True,
                            "target_barrier_family": "goal_artifact_missing_after_surface_fix",
                            "barrier_sampling_rationale": "real candidate",
                            "selection_priority_reason": "thin slice",
                            "task_definition_was_changed_for_barrier_targeting": False,
                            "barrier_sampling_audit_pass": True,
                        },
                    },
                    {
                        "task_id": "b",
                        "source_id": "source",
                        "family_id": "family",
                        "workflow_task_template_id": "template",
                        "complexity_tier": "medium",
                        "authenticity_audit": {
                            "source_provenance": "source",
                            "workflow_proximity_pass": True,
                            "anti_fake_workflow_pass": True,
                            "context_naturalness_risk": "low",
                            "goal_level_acceptance_is_realistic": True,
                            "authenticity_audit_pass": True,
                        },
                        "barrier_sampling_audit": {
                            "barrier_sampling_intent_present": True,
                            "target_barrier_family": "dispatch_or_policy_limited_unresolved",
                            "barrier_sampling_rationale": "real candidate",
                            "selection_priority_reason": "thin slice",
                            "task_definition_was_changed_for_barrier_targeting": False,
                            "barrier_sampling_audit_pass": True,
                        },
                    },
                    {
                        "task_id": "c",
                        "source_id": "source",
                        "family_id": "family",
                        "workflow_task_template_id": "template",
                        "complexity_tier": "medium",
                        "authenticity_audit": {
                            "source_provenance": "source",
                            "workflow_proximity_pass": True,
                            "anti_fake_workflow_pass": True,
                            "context_naturalness_risk": "low",
                            "goal_level_acceptance_is_realistic": True,
                            "authenticity_audit_pass": True,
                        },
                        "barrier_sampling_audit": {
                            "barrier_sampling_intent_present": True,
                            "target_barrier_family": "workflow_spillover_unresolved",
                            "barrier_sampling_rationale": "real candidate",
                            "selection_priority_reason": "thin slice",
                            "task_definition_was_changed_for_barrier_targeting": False,
                            "barrier_sampling_audit_pass": True,
                        },
                    },
                ]
            }
            governance_path.parent.mkdir(parents=True, exist_ok=True)
            governance_path.write_text(json.dumps(payload), encoding="utf-8")
            probe = build_v090_depth_probe(
                governance_pack_path=str(governance_path),
                out_dir=str(root / "probe"),
            )
            self.assertEqual(probe["candidate_depth_by_priority_barrier"], {
                "goal_artifact_missing_after_surface_fix": 1,
                "dispatch_or_policy_limited_unresolved": 1,
                "workflow_spillover_unresolved": 1,
            })
            self.assertEqual(probe["candidate_pool_governance_status"], "partial")
            self.assertFalse(probe["degraded_floor_fully_met"])
            self.assertTrue(probe["needs_additional_real_sources"])

    def test_real_baseline_builder_uses_current_ten_case_pool(self) -> None:
        rows = build_baseline_candidate_rows()
        self.assertEqual(len(rows), 10)
        barrier_counts = {}
        for row in rows:
            barrier = row["barrier_sampling_audit"]["target_barrier_family"]
            if barrier:
                barrier_counts[barrier] = barrier_counts.get(barrier, 0) + 1
        self.assertEqual(
            barrier_counts,
            {
                "goal_artifact_missing_after_surface_fix": 2,
                "dispatch_or_policy_limited_unresolved": 2,
                "workflow_spillover_unresolved": 2,
            },
        )


if __name__ == "__main__":
    unittest.main()
