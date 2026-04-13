from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_14_1_broader_change_effect_characterization import (
    build_v141_broader_change_effect_characterization,
)
from gateforge.agent_modelica_v0_14_1_broader_change_execution_pack import (
    build_v141_broader_change_execution_pack,
)
from gateforge.agent_modelica_v0_14_1_closeout import build_v141_closeout
from gateforge.agent_modelica_v0_14_1_handoff_integrity import build_v141_handoff_integrity


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_v140_closeout(path: Path, *, valid: bool = True) -> None:
    handoff_mode = "execute_first_broader_change_pack" if valid else "some_other_handoff_mode"
    _write_json(
        path,
        {
            "conclusion": {
                "version_decision": "v0_14_0_broader_change_governance_ready",
                "capability_broader_change_governance_status": "governance_ready",
                "governance_ready_for_runtime_execution": True,
                "minimum_completion_signal_pass": True,
                "named_first_broader_change_pack_ready": True,
                "v0_14_1_handoff_mode": handoff_mode,
            },
            "governance_pack": {
                "broader_change_admission": {
                    "admitted_rows": [
                        {"candidate_id": "broader_L2_execution_policy_restructuring_v1"},
                        {"candidate_id": "governed_llm_backbone_upgrade_v1"},
                    ],
                    "rejection_reason_table": [],
                }
            },
        },
    )


def _make_v140_governance_pack(path: Path) -> None:
    _write_json(
        path,
        {
            "broader_change_admission": {
                "admitted_rows": [
                    {"candidate_id": "broader_L2_execution_policy_restructuring_v1"},
                    {"candidate_id": "governed_llm_backbone_upgrade_v1"},
                ],
                "named_first_broader_change_pack_ids": [
                    "broader_L2_execution_policy_restructuring_v1",
                    "governed_llm_backbone_upgrade_v1",
                ],
            }
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
    broader_hook: bool = False,
    model_hook: bool = False,
) -> None:
    case_results = [
        {
            "task_id": f"task_{i}",
            "execution_source": execution_source,
            "broader_change_pack_enabled": pack_enabled,
            "product_gap_outcome": "goal_level_resolved" if i < workflow_resolution else (
                "surface_fix_only" if i < workflow_resolution + surface_fix_only else "unresolved"
            ),
            "goal_alignment": i < goal_alignment,
            "surface_fix_only": workflow_resolution <= i < workflow_resolution + surface_fix_only,
            "token_count": 8,
            "broader_execution_policy_restructuring_applied": broader_hook and pack_enabled,
            "governed_model_upgrade_applied": model_hook and pack_enabled,
        }
        for i in range(12)
    ]
    _write_json(
        path,
        {
            "run_status": "ready",
            "execution_source": execution_source,
            "broader_change_pack_enabled": pack_enabled,
            "run_reference": str(path),
            "case_result_table": case_results,
            "workflow_resolution_count": workflow_resolution,
            "goal_alignment_count": goal_alignment,
            "surface_fix_only_count": surface_fix_only,
            "unresolved_count": unresolved,
            "token_count_total": token_total,
        },
    )


class V141FirstBroaderChangePackFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v140 = root / "v140" / "summary.json"
            _make_v140_closeout(v140)
            payload = build_v141_handoff_integrity(v140_closeout_path=str(v140), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_on_wrong_handoff_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v140 = root / "v140" / "summary.json"
            _make_v140_closeout(v140, valid=False)
            payload = build_v141_handoff_integrity(v140_closeout_path=str(v140), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_effect_characterization_mainline_material(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gov = root / "v140_gov" / "summary.json"
            _make_v140_governance_pack(gov)
            pre = root / "pre" / "summary.json"
            post = root / "post" / "summary.json"
            _make_run_summary(pre, pack_enabled=False, workflow_resolution=1, goal_alignment=2, unresolved=11)
            _make_run_summary(
                post,
                pack_enabled=True,
                workflow_resolution=3,
                goal_alignment=4,
                unresolved=9,
                broader_hook=True,
                model_hook=True,
            )
            pack = build_v141_broader_change_execution_pack(
                v140_governance_pack_path=str(gov),
                pre_intervention_run_path=str(pre),
                post_intervention_run_path=str(post),
                out_dir=str(root / "pack"),
            )
            effect = build_v141_broader_change_effect_characterization(
                broader_change_execution_pack_path=str(root / "pack" / "summary.json"),
                out_dir=str(root / "effect"),
            )
            self.assertEqual(pack["broader_change_execution_pack_status"], "ready")
            self.assertEqual(effect["broader_change_effect_summary"]["broader_change_effect_class"], "mainline_material")

    def test_effect_characterization_side_evidence_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gov = root / "v140_gov" / "summary.json"
            _make_v140_governance_pack(gov)
            pre = root / "pre" / "summary.json"
            post = root / "post" / "summary.json"
            _make_run_summary(pre, pack_enabled=False, workflow_resolution=1, goal_alignment=2, unresolved=11)
            _make_run_summary(
                post,
                pack_enabled=True,
                workflow_resolution=1,
                goal_alignment=2,
                unresolved=11,
                broader_hook=True,
                model_hook=True,
            )
            build_v141_broader_change_execution_pack(
                v140_governance_pack_path=str(gov),
                pre_intervention_run_path=str(pre),
                post_intervention_run_path=str(post),
                out_dir=str(root / "pack"),
            )
            effect = build_v141_broader_change_effect_characterization(
                broader_change_execution_pack_path=str(root / "pack" / "summary.json"),
                out_dir=str(root / "effect"),
            )
            self.assertEqual(effect["broader_change_effect_summary"]["broader_change_effect_class"], "side_evidence_only")

    def test_effect_characterization_non_material(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gov = root / "v140_gov" / "summary.json"
            _make_v140_governance_pack(gov)
            pre = root / "pre" / "summary.json"
            post = root / "post" / "summary.json"
            _make_run_summary(pre, pack_enabled=False, workflow_resolution=1, goal_alignment=2, unresolved=11)
            _make_run_summary(post, pack_enabled=True, workflow_resolution=1, goal_alignment=2, unresolved=11)
            build_v141_broader_change_execution_pack(
                v140_governance_pack_path=str(gov),
                pre_intervention_run_path=str(pre),
                post_intervention_run_path=str(post),
                out_dir=str(root / "pack"),
            )
            effect = build_v141_broader_change_effect_characterization(
                broader_change_execution_pack_path=str(root / "pack" / "summary.json"),
                out_dir=str(root / "effect"),
            )
            self.assertEqual(effect["broader_change_effect_summary"]["broader_change_effect_class"], "non_material")

    def test_effect_characterization_invalid_when_same_execution_source_false(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            gov = root / "v140_gov" / "summary.json"
            _make_v140_governance_pack(gov)
            pre = root / "pre" / "summary.json"
            post = root / "post" / "summary.json"
            _make_run_summary(pre, pack_enabled=False, execution_source="agent_modelica_live_executor_v1")
            _make_run_summary(post, pack_enabled=True, execution_source="other_executor", broader_hook=True, model_hook=True)
            pack = build_v141_broader_change_execution_pack(
                v140_governance_pack_path=str(gov),
                pre_intervention_run_path=str(pre),
                post_intervention_run_path=str(post),
                out_dir=str(root / "pack"),
            )
            self.assertEqual(pack["broader_change_execution_pack_status"], "invalid")

    def test_effect_characterization_invalid_when_post_reference_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack = root / "pack" / "summary.json"
            _write_json(
                pack,
                {
                    "broader_change_execution_pack_status": "invalid",
                    "pre_post_broader_change_comparison_record": {
                        "pre_intervention_run_reference": "pre.json",
                        "post_intervention_run_reference": None,
                        "same_execution_source": True,
                        "same_case_requirement_met": True,
                    },
                },
            )
            effect = build_v141_broader_change_effect_characterization(
                broader_change_execution_pack_path=str(pack),
                out_dir=str(root / "effect"),
            )
            self.assertEqual(effect["broader_change_effect_summary"]["broader_change_effect_class"], "invalid")

    def test_closeout_routes_to_mainline_material(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v140 = root / "v140" / "summary.json"
            _make_v140_closeout(v140)
            gov = root / "v140_gov" / "summary.json"
            _make_v140_governance_pack(gov)
            pre = root / "pre" / "summary.json"
            post = root / "post" / "summary.json"
            _make_run_summary(pre, pack_enabled=False, workflow_resolution=1, goal_alignment=2, unresolved=11)
            _make_run_summary(
                post,
                pack_enabled=True,
                workflow_resolution=2,
                goal_alignment=3,
                unresolved=10,
                broader_hook=True,
                model_hook=True,
            )
            payload = build_v141_closeout(
                v140_closeout_path=str(v140),
                v140_governance_pack_path=str(gov),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                broader_change_execution_pack_path=str(root / "pack" / "summary.json"),
                broader_change_effect_characterization_path=str(root / "effect" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            # Build explicit artifacts so closeout consumes the prepared synthetic run pair.
            build_v141_handoff_integrity(v140_closeout_path=str(v140), out_dir=str(root / "handoff"))
            build_v141_broader_change_execution_pack(
                v140_governance_pack_path=str(gov),
                pre_intervention_run_path=str(pre),
                post_intervention_run_path=str(post),
                out_dir=str(root / "pack"),
            )
            build_v141_broader_change_effect_characterization(
                broader_change_execution_pack_path=str(root / "pack" / "summary.json"),
                out_dir=str(root / "effect"),
            )
            payload = build_v141_closeout(
                v140_closeout_path=str(v140),
                v140_governance_pack_path=str(gov),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                broader_change_execution_pack_path=str(root / "pack" / "summary.json"),
                broader_change_effect_characterization_path=str(root / "effect" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_14_1_first_broader_change_pack_mainline_material",
            )


if __name__ == "__main__":
    unittest.main()
