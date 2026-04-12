from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_12_1_closeout import build_v121_closeout
from gateforge.agent_modelica_v0_12_1_handoff_integrity import build_v121_handoff_integrity
from gateforge.agent_modelica_v0_12_1_pack_effect_characterization import (
    build_v121_pack_effect_characterization,
)
from gateforge.agent_modelica_v0_12_1_remedy_execution_pack import build_v121_remedy_execution_pack


class AgentModelicaV121FirstRemedyPackFlowTests(unittest.TestCase):
    def _write_v120_closeout(self, path: Path, *, bad_handoff: bool = False) -> None:
        payload = {
            "conclusion": {
                "version_decision": (
                    "v0_12_0_operational_remedy_inputs_invalid"
                    if bad_handoff
                    else "v0_12_0_operational_remedy_governance_ready"
                ),
                "governance_ready_for_runtime_execution": not bad_handoff,
                "named_first_remedy_pack_ready": not bad_handoff,
                "v0_12_1_handoff_mode": (
                    "rebuild_operational_remedy_governance_first"
                    if bad_handoff
                    else "execute_first_bounded_operational_remedy_pack"
                ),
            },
            "governance_pack": {
                "remedy_registry": {
                    "remedy_rows": [
                        {
                            "remedy_id": "workflow_goal_reanchoring_hardening",
                            "admission_status": "admitted",
                        },
                        {
                            "remedy_id": "dynamic_prompt_field_stability_hardening",
                            "admission_status": "admitted",
                        },
                        {
                            "remedy_id": "full_omc_error_visibility_hardening",
                            "admission_status": "admitted",
                        },
                    ]
                }
            },
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _run_payload(
        self,
        *,
        run_reference: str,
        execution_source: str = "agent_modelica_live_executor_v1",
        remedy_pack_enabled: bool,
        workflow_resolution_count: int,
        goal_alignment_count: int,
        surface_fix_only_count: int,
        unresolved_count: int,
        token_count_total: int,
        sidecar_mode: str = "strong",
    ) -> dict:
        if sidecar_mode == "strong":
            dynamic = {
                "static_prefix_stable": remedy_pack_enabled,
                "dynamic_timestamp_found": False,
                "dynamic_task_id_found": not remedy_pack_enabled,
                "absolute_path_found": False,
            }
            workflow_goal_seen = remedy_pack_enabled
            full_error_seen = remedy_pack_enabled
        else:
            dynamic = {
                "static_prefix_stable": False,
                "dynamic_timestamp_found": False,
                "dynamic_task_id_found": False,
                "absolute_path_found": False,
            }
            workflow_goal_seen = False
            full_error_seen = False
        return {
            "run_status": "ready",
            "execution_source": execution_source,
            "remedy_pack_enabled": remedy_pack_enabled,
            "run_reference": run_reference,
            "workflow_resolution_count": workflow_resolution_count,
            "goal_alignment_count": goal_alignment_count,
            "surface_fix_only_count": surface_fix_only_count,
            "unresolved_count": unresolved_count,
            "token_count_total": token_count_total,
            "case_result_table": [
                {
                    "task_id": f"case_{idx}",
                    "execution_source": execution_source,
                    "remedy_pack_enabled": remedy_pack_enabled,
                    "product_gap_outcome": "goal_level_resolved" if idx < workflow_resolution_count else "unresolved",
                    "goal_alignment": idx < goal_alignment_count,
                    "surface_fix_only": False,
                    "token_count": token_count_total // 3,
                    "workflow_goal_reanchoring_observed": workflow_goal_seen,
                    "dynamic_system_prompt_field_audit_result": dict(dynamic),
                    "full_omc_error_propagation_observed": full_error_seen,
                }
                for idx in range(3)
            ],
        }

    def test_handoff_integrity_pass_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v120 = root / "v120.json"
            self._write_v120_closeout(v120)
            payload = build_v121_handoff_integrity(
                v120_closeout_path=str(v120),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v120 = root / "v120_bad.json"
            self._write_v120_closeout(v120, bad_handoff=True)
            payload = build_v121_handoff_integrity(
                v120_closeout_path=str(v120),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_mainline_improving_pack_level_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pre = root / "pre.json"
            post = root / "post.json"
            pre.write_text(json.dumps(self._run_payload(
                run_reference="pre.json",
                remedy_pack_enabled=False,
                workflow_resolution_count=1,
                goal_alignment_count=1,
                surface_fix_only_count=0,
                unresolved_count=2,
                token_count_total=300,
                sidecar_mode="weak",
            )), encoding="utf-8")
            post.write_text(json.dumps(self._run_payload(
                run_reference="post.json",
                remedy_pack_enabled=True,
                workflow_resolution_count=2,
                goal_alignment_count=2,
                surface_fix_only_count=0,
                unresolved_count=1,
                token_count_total=320,
            )), encoding="utf-8")
            execution = build_v121_remedy_execution_pack(
                pre_remedy_run_path=str(pre),
                post_remedy_run_path=str(post),
                out_dir=str(root / "execution"),
            )
            effect = build_v121_pack_effect_characterization(
                remedy_execution_pack_path=str(root / "execution" / "summary.json"),
                out_dir=str(root / "effect"),
            )
            self.assertEqual(execution["remedy_execution_pack_status"], "ready")
            self.assertEqual(effect["pack_level_effect_summary"]["pack_level_effect"], "mainline_improving")

    def test_side_evidence_only_pack_level_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pre = root / "pre.json"
            post = root / "post.json"
            pre.write_text(json.dumps(self._run_payload(
                run_reference="pre.json",
                remedy_pack_enabled=False,
                workflow_resolution_count=1,
                goal_alignment_count=1,
                surface_fix_only_count=0,
                unresolved_count=2,
                token_count_total=300,
                sidecar_mode="weak",
            )), encoding="utf-8")
            post.write_text(json.dumps(self._run_payload(
                run_reference="post.json",
                remedy_pack_enabled=True,
                workflow_resolution_count=1,
                goal_alignment_count=1,
                surface_fix_only_count=0,
                unresolved_count=2,
                token_count_total=260,
            )), encoding="utf-8")
            build_v121_remedy_execution_pack(
                pre_remedy_run_path=str(pre),
                post_remedy_run_path=str(post),
                out_dir=str(root / "execution"),
            )
            effect = build_v121_pack_effect_characterization(
                remedy_execution_pack_path=str(root / "execution" / "summary.json"),
                out_dir=str(root / "effect"),
            )
            self.assertEqual(effect["pack_level_effect_summary"]["pack_level_effect"], "side_evidence_only")

    def test_non_material_pack_level_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pre = root / "pre.json"
            post = root / "post.json"
            payload = self._run_payload(
                run_reference="same.json",
                remedy_pack_enabled=False,
                workflow_resolution_count=1,
                goal_alignment_count=1,
                surface_fix_only_count=0,
                unresolved_count=2,
                token_count_total=300,
                sidecar_mode="weak",
            )
            pre.write_text(json.dumps(payload), encoding="utf-8")
            payload["remedy_pack_enabled"] = True
            payload["run_reference"] = "post.json"
            post.write_text(json.dumps(payload), encoding="utf-8")
            build_v121_remedy_execution_pack(
                pre_remedy_run_path=str(pre),
                post_remedy_run_path=str(post),
                out_dir=str(root / "execution"),
            )
            effect = build_v121_pack_effect_characterization(
                remedy_execution_pack_path=str(root / "execution" / "summary.json"),
                out_dir=str(root / "effect"),
            )
            self.assertEqual(effect["pack_level_effect_summary"]["pack_level_effect"], "non_material")

    def test_execution_invalid_on_missing_post_run(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pre = root / "pre.json"
            pre.write_text(json.dumps(self._run_payload(
                run_reference="pre.json",
                remedy_pack_enabled=False,
                workflow_resolution_count=1,
                goal_alignment_count=1,
                surface_fix_only_count=0,
                unresolved_count=2,
                token_count_total=300,
                sidecar_mode="weak",
            )), encoding="utf-8")
            execution = build_v121_remedy_execution_pack(
                pre_remedy_run_path=str(pre),
                post_remedy_run_path="",
                buildings_fixture_hardpack_path=str(root / "missing_buildings.json"),
                openipsl_fixture_hardpack_path=str(root / "missing_openipsl.json"),
                v112_product_gap_substrate_builder_path=str(root / "missing_v112.json"),
                out_dir=str(root / "execution"),
            )
            self.assertEqual(execution["remedy_execution_pack_status"], "invalid")

    def test_execution_invalid_when_same_execution_source_is_false(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pre = root / "pre.json"
            post = root / "post.json"
            pre.write_text(json.dumps(self._run_payload(
                run_reference="pre.json",
                execution_source="frozen_product_gap_substrate_deterministic_replay",
                remedy_pack_enabled=False,
                workflow_resolution_count=1,
                goal_alignment_count=1,
                surface_fix_only_count=0,
                unresolved_count=2,
                token_count_total=300,
            )), encoding="utf-8")
            post.write_text(json.dumps(self._run_payload(
                run_reference="post.json",
                execution_source="agent_modelica_live_executor_v1",
                remedy_pack_enabled=True,
                workflow_resolution_count=1,
                goal_alignment_count=1,
                surface_fix_only_count=0,
                unresolved_count=2,
                token_count_total=260,
            )), encoding="utf-8")
            build_v121_remedy_execution_pack(
                pre_remedy_run_path=str(pre),
                post_remedy_run_path=str(post),
                out_dir=str(root / "execution"),
            )
            effect = build_v121_pack_effect_characterization(
                remedy_execution_pack_path=str(root / "execution" / "summary.json"),
                out_dir=str(root / "effect"),
            )
            self.assertEqual(effect["pack_level_effect_summary"]["pack_level_effect"], "invalid")

    def test_closeout_routes_correctly_on_mainline_improving(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v120 = root / "v120.json"
            self._write_v120_closeout(v120)
            pre = root / "pre.json"
            post = root / "post.json"
            pre.write_text(json.dumps(self._run_payload(
                run_reference="pre.json",
                remedy_pack_enabled=False,
                workflow_resolution_count=1,
                goal_alignment_count=1,
                surface_fix_only_count=0,
                unresolved_count=2,
                token_count_total=300,
                sidecar_mode="weak",
            )), encoding="utf-8")
            post.write_text(json.dumps(self._run_payload(
                run_reference="post.json",
                remedy_pack_enabled=True,
                workflow_resolution_count=2,
                goal_alignment_count=2,
                surface_fix_only_count=0,
                unresolved_count=1,
                token_count_total=260,
            )), encoding="utf-8")
            build_v121_handoff_integrity(
                v120_closeout_path=str(v120),
                out_dir=str(root / "integrity"),
            )
            build_v121_remedy_execution_pack(
                pre_remedy_run_path=str(pre),
                post_remedy_run_path=str(post),
                out_dir=str(root / "execution"),
            )
            build_v121_pack_effect_characterization(
                remedy_execution_pack_path=str(root / "execution" / "summary.json"),
                out_dir=str(root / "effect"),
            )
            payload = build_v121_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                remedy_execution_pack_path=str(root / "execution" / "summary.json"),
                pack_effect_characterization_path=str(root / "effect" / "summary.json"),
                v120_closeout_path=str(v120),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_12_1_first_remedy_pack_mainline_improving",
            )


if __name__ == "__main__":
    unittest.main()
