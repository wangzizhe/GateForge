from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_9_1_candidate_source_admission import build_v091_candidate_source_admission
from gateforge.agent_modelica_v0_9_1_closeout import build_v091_closeout
from gateforge.agent_modelica_v0_9_1_handoff_integrity import build_v091_handoff_integrity
from gateforge.agent_modelica_v0_9_1_pool_delta_build import build_v091_pool_delta


def _write_v090_closeout(path: Path, *, version_decision: str = "v0_9_0_candidate_pool_governance_partial") -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "candidate_pool_governance_status": "partial",
            "candidate_depth_by_priority_barrier": {
                "goal_artifact_missing_after_surface_fix": 2,
                "dispatch_or_policy_limited_unresolved": 2,
                "workflow_spillover_unresolved": 2,
            },
            "needs_additional_real_sources": True,
            "v0_9_1_handoff_mode": "expand_real_candidate_pool_before_substrate_freeze",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v090_governance_pack(path: Path) -> None:
    rows = []
    for barrier in (
        "goal_artifact_missing_after_surface_fix",
        "goal_artifact_missing_after_surface_fix",
        "dispatch_or_policy_limited_unresolved",
        "dispatch_or_policy_limited_unresolved",
        "workflow_spillover_unresolved",
        "workflow_spillover_unresolved",
    ):
        rows.append(
            {
                "task_id": f"baseline_{len(rows)}",
                "source_id": "baseline",
                "family_id": "family",
                "workflow_task_template_id": "template",
                "complexity_tier": "medium",
                "authenticity_audit": {
                    "source_provenance": "baseline",
                    "workflow_proximity_pass": True,
                    "anti_fake_workflow_pass": True,
                    "context_naturalness_risk": "low",
                    "goal_level_acceptance_is_realistic": True,
                    "authenticity_audit_pass": True,
                },
                "barrier_sampling_audit": {
                    "barrier_sampling_intent_present": True,
                    "target_barrier_family": barrier,
                    "barrier_sampling_rationale": "baseline",
                    "selection_priority_reason": "baseline",
                    "task_definition_was_changed_for_barrier_targeting": False,
                    "barrier_sampling_audit_pass": True,
                },
            }
        )
    payload = {"baseline_candidate_rows": rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_challenge_taskset(path: Path) -> None:
    tasks = []
    for idx, failure_type in enumerate(["semantic_regression", "semantic_regression", "semantic_regression", "model_check_error", "model_check_error", "model_check_error", "simulate_error", "simulate_error", "simulate_error"]):
        tasks.append(
            {
                "task_id": f"electrical_case_{idx}_{failure_type}",
                "scale": "medium",
                "failure_type": failure_type,
                "expected_stage": "check" if failure_type == "model_check_error" else "simulate",
                "origin_task_id": "medium_dual_source_v0" if idx < 3 else "medium_parallel_rc_v0" if idx < 6 else "small_r_divider_v0",
            }
        )
    payload = {"tasks": tasks}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_holdout_taskset(path: Path, summary_path: Path) -> None:
    payload = {
        "tasks": [
            {
                "task_id": "trap_case",
                "scale": "small",
                "failure_type": "false_friend_patch_trap",
                "expected_stage": "simulate",
                "origin_task_id": "trap_case",
            }
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")


class AgentModelicaV091SourceExpansionFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v090_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v090 = root / "v090" / "summary.json"
            _write_v090_closeout(v090)
            payload = build_v091_handoff_integrity(v090_closeout_path=str(v090), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_source_admission_admits_challenge_source_and_rejects_holdout(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            challenge = root / "challenge" / "taskset_frozen.json"
            holdout = root / "holdout" / "taskset_frozen.json"
            holdout_summary = root / "holdout" / "summary.json"
            _write_challenge_taskset(challenge)
            _write_holdout_taskset(holdout, holdout_summary)
            from gateforge import agent_modelica_v0_9_1_candidate_source_admission as mod

            original = mod.SOURCE_DISCOVERY_SPECS
            mod.SOURCE_DISCOVERY_SPECS = [
                {
                    "source_id": "challenge",
                    "taskset_path": str(challenge),
                    "summary_path": "",
                    "source_type": "challenge_pack_frozen",
                    "source_collection_method": "artifact",
                    "source_provenance_description": "challenge",
                    "source_authenticity_risk_level": "medium",
                },
                {
                    "source_id": "holdout",
                    "taskset_path": str(holdout),
                    "summary_path": str(holdout_summary),
                    "source_type": "layer4_holdout_frozen",
                    "source_collection_method": "artifact",
                    "source_provenance_description": "holdout",
                    "source_authenticity_risk_level": "high",
                },
            ]
            try:
                payload = build_v091_candidate_source_admission(out_dir=str(root / "admission"))
            finally:
                mod.SOURCE_DISCOVERY_SPECS = original
            self.assertEqual(payload["candidate_source_expansion_ledger"]["admitted_source_count"], 1)
            self.assertEqual(payload["candidate_source_expansion_ledger"]["rejected_source_count"], 1)

    def test_pool_delta_can_reach_ready_with_balanced_new_source(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            governance = root / "governance" / "summary.json"
            admission = root / "admission" / "summary.json"
            _write_v090_governance_pack(governance)
            challenge_rows = []
            for barrier in (
                "goal_artifact_missing_after_surface_fix",
                "goal_artifact_missing_after_surface_fix",
                "goal_artifact_missing_after_surface_fix",
                "dispatch_or_policy_limited_unresolved",
                "dispatch_or_policy_limited_unresolved",
                "dispatch_or_policy_limited_unresolved",
                "workflow_spillover_unresolved",
                "workflow_spillover_unresolved",
                "workflow_spillover_unresolved",
            ):
                challenge_rows.append(
                    {
                        "task_id": f"new_{len(challenge_rows)}",
                        "source_id": "challenge",
                        "family_id": "family",
                        "workflow_task_template_id": "template",
                        "complexity_tier": "medium",
                        "authenticity_audit": {
                            "source_provenance": "challenge",
                            "workflow_proximity_pass": True,
                            "anti_fake_workflow_pass": True,
                            "context_naturalness_risk": "medium",
                            "goal_level_acceptance_is_realistic": True,
                            "authenticity_audit_pass": True,
                        },
                        "barrier_sampling_audit": {
                            "barrier_sampling_intent_present": True,
                            "target_barrier_family": barrier,
                            "barrier_sampling_rationale": "new",
                            "selection_priority_reason": "new",
                            "task_definition_was_changed_for_barrier_targeting": False,
                            "barrier_sampling_audit_pass": True,
                        },
                    }
                )
            admission_payload = {
                "candidate_source_intake_table": [
                    {
                        "source_id": "challenge",
                        "source_admission_pass": True,
                        "candidate_rows": challenge_rows,
                    }
                ]
            }
            admission.parent.mkdir(parents=True, exist_ok=True)
            admission.write_text(json.dumps(admission_payload), encoding="utf-8")
            payload = build_v091_pool_delta(
                v090_governance_pack_path=str(governance),
                source_admission_path=str(admission),
                out_dir=str(root / "pool"),
            )
            self.assertEqual(payload["post_expansion_candidate_pool_count"], 15)
            self.assertTrue(payload["meaningful_growth_source_present"])
            self.assertEqual(payload["candidate_depth_by_priority_barrier"]["goal_artifact_missing_after_surface_fix"], 5)

    def test_closeout_routes_to_ready_when_every_barrier_reaches_five(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v090 = root / "v090" / "summary.json"
            governance = root / "governance" / "summary.json"
            _write_v090_closeout(v090)
            _write_v090_governance_pack(governance)
            challenge = root / "challenge" / "taskset_frozen.json"
            holdout = root / "holdout" / "taskset_frozen.json"
            holdout_summary = root / "holdout" / "summary.json"
            _write_challenge_taskset(challenge)
            _write_holdout_taskset(holdout, holdout_summary)
            from gateforge import agent_modelica_v0_9_1_candidate_source_admission as mod

            original = mod.SOURCE_DISCOVERY_SPECS
            mod.SOURCE_DISCOVERY_SPECS = [
                {
                    "source_id": "challenge",
                    "taskset_path": str(challenge),
                    "summary_path": "",
                    "source_type": "challenge_pack_frozen",
                    "source_collection_method": "artifact",
                    "source_provenance_description": "challenge",
                    "source_authenticity_risk_level": "medium",
                },
                {
                    "source_id": "holdout",
                    "taskset_path": str(holdout),
                    "summary_path": str(holdout_summary),
                    "source_type": "layer4_holdout_frozen",
                    "source_collection_method": "artifact",
                    "source_provenance_description": "holdout",
                    "source_authenticity_risk_level": "high",
                },
            ]
            try:
                payload = build_v091_closeout(
                    handoff_integrity_path=str(root / "handoff" / "summary.json"),
                    source_admission_path=str(root / "admission" / "summary.json"),
                    pool_delta_path=str(root / "pool" / "summary.json"),
                    v090_closeout_path=str(v090),
                    v090_governance_pack_path=str(governance),
                    out_dir=str(root / "closeout"),
                )
            finally:
                mod.SOURCE_DISCOVERY_SPECS = original
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_1_real_candidate_source_expansion_ready")

    def test_closeout_routes_to_partial_when_growth_is_real_but_barriers_remain_below_five(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v090 = root / "v090" / "summary.json"
            governance = root / "governance" / "summary.json"
            _write_v090_closeout(v090)
            _write_v090_governance_pack(governance)

            partial_rows = []
            for barrier in (
                "goal_artifact_missing_after_surface_fix",
                "dispatch_or_policy_limited_unresolved",
                "workflow_spillover_unresolved",
                "goal_artifact_missing_after_surface_fix",
                "dispatch_or_policy_limited_unresolved",
                "workflow_spillover_unresolved",
            ):
                partial_rows.append(
                    {
                        "task_id": f"partial_{len(partial_rows)}",
                        "source_id": "challenge_partial",
                        "family_id": "family",
                        "workflow_task_template_id": "template",
                        "complexity_tier": "medium",
                        "authenticity_audit": {
                            "source_provenance": "challenge_partial",
                            "workflow_proximity_pass": True,
                            "anti_fake_workflow_pass": True,
                            "context_naturalness_risk": "medium",
                            "goal_level_acceptance_is_realistic": True,
                            "authenticity_audit_pass": True,
                        },
                        "barrier_sampling_audit": {
                            "barrier_sampling_intent_present": True,
                            "target_barrier_family": barrier,
                            "barrier_sampling_rationale": "partial-growth",
                            "selection_priority_reason": "partial-growth",
                            "task_definition_was_changed_for_barrier_targeting": False,
                            "barrier_sampling_audit_pass": True,
                        },
                    }
                )

            admission_payload = {
                "candidate_source_intake_table": [
                    {
                        "source_id": "challenge_partial",
                        "source_admission_pass": True,
                        "candidate_rows": partial_rows,
                    }
                ]
            }
            admission_path = root / "admission" / "summary.json"
            admission_path.parent.mkdir(parents=True, exist_ok=True)
            admission_path.write_text(json.dumps(admission_payload), encoding="utf-8")

            payload = build_v091_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                source_admission_path=str(admission_path),
                pool_delta_path=str(root / "pool" / "summary.json"),
                v090_closeout_path=str(v090),
                v090_governance_pack_path=str(governance),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_1_real_candidate_source_expansion_partial")
            self.assertEqual(
                payload["conclusion"]["v0_9_2_handoff_mode"],
                "continue_expanding_real_candidate_sources",
            )
            self.assertEqual(
                payload["conclusion"]["candidate_depth_by_priority_barrier"],
                {
                    "goal_artifact_missing_after_surface_fix": 4,
                    "dispatch_or_policy_limited_unresolved": 4,
                    "workflow_spillover_unresolved": 4,
                },
            )


if __name__ == "__main__":
    unittest.main()
