from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_13_1_capability_effect_characterization import (
    build_v131_capability_effect_characterization,
)
from gateforge.agent_modelica_v0_13_1_capability_intervention_execution_pack import (
    build_v131_capability_intervention_execution_pack,
)
from gateforge.agent_modelica_v0_13_1_closeout import build_v131_closeout
from gateforge.agent_modelica_v0_13_1_handoff_integrity import build_v131_handoff_integrity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_v130_closeout(path: Path, *, valid: bool = True) -> None:
    handoff_mode = (
        "execute_first_bounded_capability_intervention_pack"
        if valid
        else "some_other_handoff_mode"
    )
    _write_json(
        path,
        {
            "conclusion": {
                "version_decision": "v0_13_0_capability_intervention_governance_ready",
                "capability_intervention_governance_status": "governance_ready",
                "governance_ready_for_runtime_execution": True,
                "minimum_completion_signal_pass": True,
                "named_first_intervention_pack_ready": True,
                "v0_13_1_handoff_mode": handoff_mode,
            },
            "governance_pack": {
                "capability_intervention_admission": {
                    "admitted_rows": [
                        {"intervention_id": "bounded_execution_strategy_upgrade_v1"},
                        {"intervention_id": "bounded_replan_search_control_upgrade_v1"},
                        {"intervention_id": "bounded_failure_diagnosis_upgrade_v1"},
                    ],
                    "rejection_reason_table": [],
                }
            },
        },
    )


def _make_run_summary(
    path: Path,
    *,
    pack_enabled: bool,
    workflow_resolution: int = 0,
    goal_alignment: int = 0,
    surface_fix_only: int = 0,
    unresolved: int = 12,
    token_total: int = 100,
    execution_source: str = "agent_modelica_live_executor_v1",
    same_source_override: bool | None = None,
) -> None:
    case_results = [
        {
            "task_id": f"task_{i}",
            "execution_source": execution_source,
            "capability_intervention_pack_enabled": pack_enabled,
            "product_gap_outcome": "goal_level_resolved" if i < workflow_resolution else (
                "surface_fix_only" if i < workflow_resolution + surface_fix_only else "unresolved"
            ),
            "goal_alignment": i < goal_alignment,
            "surface_fix_only": workflow_resolution <= i < workflow_resolution + surface_fix_only,
            "token_count": 8,
            "workflow_goal_reanchoring_observed": False,
            "execution_strategy_upgrade_applied": pack_enabled,
            "replan_search_control_upgrade_applied": pack_enabled,
            "failure_diagnosis_upgrade_applied": pack_enabled,
        }
        for i in range(12)
    ]
    _write_json(
        path,
        {
            "run_status": "ready",
            "execution_source": execution_source,
            "capability_intervention_pack_enabled": pack_enabled,
            "run_reference": str(path),
            "case_result_table": case_results,
            "workflow_resolution_count": workflow_resolution,
            "goal_alignment_count": goal_alignment,
            "surface_fix_only_count": surface_fix_only,
            "unresolved_count": unresolved,
            "token_count_total": token_total,
        },
    )


def _make_execution_pack(
    root: Path,
    *,
    pre_path: Path,
    post_path: Path,
    same_execution_source: bool = True,
    pack_status: str = "ready",
) -> Path:
    pre = json.loads(pre_path.read_text(encoding="utf-8"))
    post = json.loads(post_path.read_text(encoding="utf-8"))
    pre_source = str(pre.get("execution_source") or "")
    post_source = str(post.get("execution_source") or "")
    actual_same = pre_source == "agent_modelica_live_executor_v1" and post_source == "agent_modelica_live_executor_v1"
    effective_same = same_execution_source and actual_same
    pre_resolution = int(pre.get("workflow_resolution_count") or 0)
    post_resolution = int(post.get("workflow_resolution_count") or 0)
    pre_goal = int(pre.get("goal_alignment_count") or 0)
    post_goal = int(post.get("goal_alignment_count") or 0)
    pre_surface = int(pre.get("surface_fix_only_count") or 0)
    post_surface = int(post.get("surface_fix_only_count") or 0)
    pre_unresolved = int(pre.get("unresolved_count") or 0)
    post_unresolved = int(post.get("unresolved_count") or 0)
    pre_token = int(pre.get("token_count_total") or 0)
    post_token = int(post.get("token_count_total") or 0)
    token_delta = post_token - pre_token

    post_rows = list(post.get("case_result_table") or [])
    pack_enabled_in_post = bool(post.get("capability_intervention_pack_enabled"))
    intervention_rows = [
        {
            "intervention_id": "bounded_execution_strategy_upgrade_v1",
            "intervention_family": "capability_level_execution_strategy_improvement",
            "intervention_execution_shape": "composite_capability_patch",
            "bounded_change_surface": "L2_structured_plan_and_execution_strategy_upgrade",
            "intervention_enabled": bool(
                pack_enabled_in_post
                and any(bool(r.get("execution_strategy_upgrade_applied")) for r in post_rows)
            ),
            "carried_baseline_reference": "v0_13_0_governance_pack.admitted_intervention_set",
        },
        {
            "intervention_id": "bounded_replan_search_control_upgrade_v1",
            "intervention_family": "search_control_and_replan_improvement",
            "intervention_execution_shape": "composite_capability_patch",
            "bounded_change_surface": "L2_replan_policy_and_search_budget_control_upgrade",
            "intervention_enabled": bool(
                pack_enabled_in_post
                and any(bool(r.get("replan_search_control_upgrade_applied")) for r in post_rows)
            ),
            "carried_baseline_reference": "v0_13_0_governance_pack.admitted_intervention_set",
        },
        {
            "intervention_id": "bounded_failure_diagnosis_upgrade_v1",
            "intervention_family": "failure_state_diagnosis_improvement",
            "intervention_execution_shape": "composite_capability_patch",
            "bounded_change_surface": "L3_L4_failure_bucket_and_diagnosis_chain_upgrade",
            "intervention_enabled": bool(
                pack_enabled_in_post
                and any(bool(r.get("failure_diagnosis_upgrade_applied")) for r in post_rows)
            ),
            "carried_baseline_reference": "v0_13_0_governance_pack.admitted_intervention_set",
        },
    ]
    all_enabled = all(bool(r.get("intervention_enabled")) for r in intervention_rows)

    measurable_fields = []
    if token_delta != 0:
        measurable_fields.append("token_count_delta")
    for field in ("execution_strategy_upgrade_applied", "replan_search_control_upgrade_applied", "failure_diagnosis_upgrade_applied"):
        pre_rows = list(pre.get("case_result_table") or [])
        post_rows_check = list(post.get("case_result_table") or [])
        pre_any = any(bool(r.get(field)) for r in pre_rows)
        post_any = any(bool(r.get(field)) for r in post_rows_check)
        if not pre_any and post_any:
            measurable_fields.append(field)

    resolution_delta = post_resolution - pre_resolution
    goal_alignment_delta = post_goal - pre_goal
    sidecar_status = (
        "measurable_runtime_side_evidence_movement" if measurable_fields else "no_measurable_runtime_side_evidence_movement"
    )

    actual_pack_status = pack_status
    if not effective_same or not all_enabled:
        actual_pack_status = "invalid"

    pack_path = root / "execution_pack" / "summary.json"
    _write_json(
        pack_path,
        {
            "capability_intervention_execution_pack_status": actual_pack_status,
            "pre_intervention_live_run": pre,
            "post_intervention_live_run": post,
            "pre_post_capability_comparison_record": {
                "pre_intervention_run_reference": str(pre_path),
                "post_intervention_run_reference": str(post_path),
                "comparison_mode": "pre_vs_post_on_same_cases",
                "same_execution_source": effective_same,
                "same_case_requirement_met": True,
                "runtime_measurement_source": "agent_modelica_live_executor_v1",
                "pre_intervention_workflow_resolution_count": pre_resolution,
                "pre_intervention_goal_alignment_count": pre_goal,
                "pre_intervention_surface_fix_only_count": pre_surface,
                "pre_intervention_unresolved_count": pre_unresolved,
                "post_intervention_workflow_resolution_count": post_resolution,
                "post_intervention_goal_alignment_count": post_goal,
                "post_intervention_surface_fix_only_count": post_surface,
                "post_intervention_unresolved_count": post_unresolved,
                "workflow_resolution_delta": resolution_delta,
                "goal_alignment_delta": goal_alignment_delta,
                "surface_fix_only_delta": post_surface - pre_surface,
                "unresolved_delta": post_unresolved - pre_unresolved,
                "token_count_delta": token_delta,
                "product_gap_sidecar_comparison_status": sidecar_status,
                "measurable_side_evidence_fields": measurable_fields,
                "ambiguous_side_evidence_movement": False,
            },
            "capability_intervention_execution_pack": {"intervention_rows": intervention_rows},
        },
    )
    return pack_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class V131FirstCapabilityInterventionPackFlowTests(unittest.TestCase):

    # 1. Handoff integrity pass path
    def test_handoff_integrity_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v130 = root / "v130" / "summary.json"
            _make_v130_closeout(v130)
            payload = build_v131_handoff_integrity(
                v130_closeout_path=str(v130),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    # 2. Handoff integrity invalid path
    def test_handoff_integrity_invalid_on_wrong_handoff_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v130 = root / "v130" / "summary.json"
            _make_v130_closeout(v130, valid=False)
            payload = build_v131_handoff_integrity(
                v130_closeout_path=str(v130),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    # 3. mainline_material path (positive workflow_resolution_delta)
    def test_effect_characterization_mainline_material(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pre = root / "pre" / "summary.json"
            post = root / "post" / "summary.json"
            _make_run_summary(pre, pack_enabled=False, workflow_resolution=0, goal_alignment=0, unresolved=12)
            _make_run_summary(post, pack_enabled=True, workflow_resolution=3, goal_alignment=3, unresolved=9)
            pack_path = _make_execution_pack(root, pre_path=pre, post_path=post)
            payload = build_v131_capability_effect_characterization(
                capability_intervention_execution_pack_path=str(pack_path),
                out_dir=str(root / "effect"),
            )
            effect = (payload.get("intervention_effect_summary") or {}).get("intervention_effect_class")
            self.assertEqual(effect, "material")

    # 4. side_evidence_only path (no mainline movement, measurable side-evidence)
    def test_effect_characterization_side_evidence_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pre = root / "pre" / "summary.json"
            post = root / "post" / "summary.json"
            _make_run_summary(pre, pack_enabled=False, workflow_resolution=0, goal_alignment=0, unresolved=12, token_total=100)
            _make_run_summary(post, pack_enabled=True, workflow_resolution=0, goal_alignment=0, unresolved=12, token_total=200)
            pack_path = _make_execution_pack(root, pre_path=pre, post_path=post)
            payload = build_v131_capability_effect_characterization(
                capability_intervention_execution_pack_path=str(pack_path),
                out_dir=str(root / "effect"),
            )
            effect = (payload.get("intervention_effect_summary") or {}).get("intervention_effect_class")
            self.assertEqual(effect, "side_evidence_only")

    # 5. non_material path (no movement on any metric)
    def test_effect_characterization_non_material(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pre = root / "pre" / "summary.json"
            post = root / "post" / "summary.json"
            # Make post also pack_enabled=False so no side evidence fields differ and token same
            _make_run_summary(pre, pack_enabled=False, workflow_resolution=0, goal_alignment=0, unresolved=12, token_total=100)
            # Override: pack_enabled=True but same token total and all zeros
            _write_json(
                post,
                {
                    "run_status": "ready",
                    "execution_source": "agent_modelica_live_executor_v1",
                    "capability_intervention_pack_enabled": True,
                    "run_reference": str(post),
                    "case_result_table": [
                        {
                            "task_id": f"task_{i}",
                            "execution_source": "agent_modelica_live_executor_v1",
                            "capability_intervention_pack_enabled": True,
                            "product_gap_outcome": "unresolved",
                            "goal_alignment": False,
                            "surface_fix_only": False,
                            "token_count": 8,
                            "workflow_goal_reanchoring_observed": False,
                            "execution_strategy_upgrade_applied": True,
                            "replan_search_control_upgrade_applied": True,
                            "failure_diagnosis_upgrade_applied": True,
                        }
                        for i in range(12)
                    ],
                    "workflow_resolution_count": 0,
                    "goal_alignment_count": 0,
                    "surface_fix_only_count": 0,
                    "unresolved_count": 12,
                    "token_count_total": 100,
                },
            )
            # Build pack manually with no token delta and no side field change
            pack_path = root / "execution_pack" / "summary.json"
            _write_json(
                pack_path,
                {
                    "capability_intervention_execution_pack_status": "ready",
                    "pre_post_capability_comparison_record": {
                        "pre_intervention_run_reference": str(pre),
                        "post_intervention_run_reference": str(post),
                        "comparison_mode": "pre_vs_post_on_same_cases",
                        "same_execution_source": True,
                        "same_case_requirement_met": True,
                        "runtime_measurement_source": "agent_modelica_live_executor_v1",
                        "pre_intervention_workflow_resolution_count": 0,
                        "pre_intervention_goal_alignment_count": 0,
                        "pre_intervention_surface_fix_only_count": 0,
                        "pre_intervention_unresolved_count": 12,
                        "post_intervention_workflow_resolution_count": 0,
                        "post_intervention_goal_alignment_count": 0,
                        "post_intervention_surface_fix_only_count": 0,
                        "post_intervention_unresolved_count": 12,
                        "workflow_resolution_delta": 0,
                        "goal_alignment_delta": 0,
                        "surface_fix_only_delta": 0,
                        "unresolved_delta": 0,
                        "token_count_delta": 0,
                        "product_gap_sidecar_comparison_status": "no_measurable_runtime_side_evidence_movement",
                        "measurable_side_evidence_fields": [],
                        "ambiguous_side_evidence_movement": False,
                    },
                    "capability_intervention_execution_pack": {
                        "intervention_rows": [
                            {"intervention_id": "bounded_execution_strategy_upgrade_v1", "intervention_enabled": True},
                            {"intervention_id": "bounded_replan_search_control_upgrade_v1", "intervention_enabled": True},
                            {"intervention_id": "bounded_failure_diagnosis_upgrade_v1", "intervention_enabled": True},
                        ]
                    },
                },
            )
            payload = build_v131_capability_effect_characterization(
                capability_intervention_execution_pack_path=str(pack_path),
                out_dir=str(root / "effect"),
            )
            effect = (payload.get("intervention_effect_summary") or {}).get("intervention_effect_class")
            self.assertEqual(effect, "non_material")

    # 6. execution_invalid path on missing post-intervention run evidence
    def test_effect_characterization_invalid_on_missing_post_ref(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack_path = root / "execution_pack" / "summary.json"
            _write_json(
                pack_path,
                {
                    "capability_intervention_execution_pack_status": "invalid",
                    "pre_post_capability_comparison_record": {
                        "pre_intervention_run_reference": str(root / "pre.json"),
                        "post_intervention_run_reference": None,
                        "comparison_mode": "pre_vs_post_on_same_cases",
                        "same_execution_source": True,
                        "same_case_requirement_met": True,
                        "runtime_measurement_source": "agent_modelica_live_executor_v1",
                        "workflow_resolution_delta": 0,
                        "goal_alignment_delta": 0,
                        "surface_fix_only_delta": 0,
                        "unresolved_delta": 0,
                        "token_count_delta": 0,
                        "product_gap_sidecar_comparison_status": "no_measurable_runtime_side_evidence_movement",
                        "measurable_side_evidence_fields": [],
                        "ambiguous_side_evidence_movement": False,
                    },
                },
            )
            payload = build_v131_capability_effect_characterization(
                capability_intervention_execution_pack_path=str(pack_path),
                out_dir=str(root / "effect"),
            )
            effect = (payload.get("intervention_effect_summary") or {}).get("intervention_effect_class")
            self.assertEqual(effect, "invalid")

    # 7. execution_invalid path when same_execution_source = false
    def test_effect_characterization_invalid_on_different_execution_source(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack_path = root / "execution_pack" / "summary.json"
            _write_json(
                pack_path,
                {
                    "capability_intervention_execution_pack_status": "invalid",
                    "pre_post_capability_comparison_record": {
                        "pre_intervention_run_reference": str(root / "pre.json"),
                        "post_intervention_run_reference": str(root / "post.json"),
                        "comparison_mode": "pre_vs_post_on_same_cases",
                        "same_execution_source": False,
                        "same_case_requirement_met": True,
                        "runtime_measurement_source": "agent_modelica_live_executor_v1",
                        "workflow_resolution_delta": 0,
                        "goal_alignment_delta": 0,
                        "surface_fix_only_delta": 0,
                        "unresolved_delta": 0,
                        "token_count_delta": 0,
                        "product_gap_sidecar_comparison_status": "no_measurable_runtime_side_evidence_movement",
                        "measurable_side_evidence_fields": [],
                        "ambiguous_side_evidence_movement": False,
                    },
                },
            )
            payload = build_v131_capability_effect_characterization(
                capability_intervention_execution_pack_path=str(pack_path),
                out_dir=str(root / "effect"),
            )
            effect = (payload.get("intervention_effect_summary") or {}).get("intervention_effect_class")
            self.assertEqual(effect, "invalid")

    # 8. closeout routes correctly on mainline_material
    def test_closeout_routes_to_mainline_material(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v130 = root / "v130" / "summary.json"
            _make_v130_closeout(v130)
            pre = root / "pre" / "summary.json"
            post = root / "post" / "summary.json"
            _make_run_summary(pre, pack_enabled=False, workflow_resolution=0, goal_alignment=0, unresolved=12)
            _make_run_summary(post, pack_enabled=True, workflow_resolution=3, goal_alignment=3, unresolved=9)
            pack_path = _make_execution_pack(root, pre_path=pre, post_path=post)
            effect_path = root / "effect" / "summary.json"
            build_v131_capability_effect_characterization(
                capability_intervention_execution_pack_path=str(pack_path),
                out_dir=str(root / "effect"),
            )
            payload = build_v131_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                capability_intervention_execution_pack_path=str(pack_path),
                capability_effect_characterization_path=str(effect_path),
                v130_closeout_path=str(v130),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_13_1_first_capability_intervention_pack_mainline_material",
            )
            self.assertEqual(
                payload["conclusion"]["v0_13_2_handoff_mode"],
                "characterize_first_capability_effect_profile",
            )


if __name__ == "__main__":
    unittest.main()
