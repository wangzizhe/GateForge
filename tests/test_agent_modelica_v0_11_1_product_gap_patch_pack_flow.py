from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_v0_11_1_bounded_validation_pack import build_v111_bounded_validation_pack
from gateforge.agent_modelica_v0_11_1_closeout import build_v111_closeout
from gateforge.agent_modelica_v0_11_1_handoff_integrity import build_v111_handoff_integrity
from gateforge.agent_modelica_v0_11_1_patch_pack_execution import build_v111_patch_pack_execution


def _write_v110_closeout(path: Path, *, next_handoff: str = "execute_first_product_gap_patch_pack") -> None:
    payload = {
        "conclusion": {
            "version_decision": "v0_11_0_product_gap_governance_ready",
            "product_gap_governance_status": "ready",
            "context_contract_status": "ready",
            "anti_reward_hacking_checklist_status": "ready",
            "product_gap_sidecar_status": "ready",
            "protocol_robustness_scope_status": "ready",
            "patch_candidate_pack_status": "ready",
            "baseline_anchor_pass": True,
            "v0_11_1_handoff_mode": next_handoff,
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v110_governance_pack(path: Path) -> None:
    payload = {
        "patch_candidates": {
            "workflow_goal_reanchoring_patch_candidate": {
                "candidate_name": "workflow_goal_reanchoring_patch_candidate",
                "target_problem": "goal drift",
                "expected_effect": "lower surface_fix_only_rate",
            },
            "system_prompt_dynamic_field_audit_patch_candidate": {
                "candidate_name": "system_prompt_dynamic_field_audit_patch_candidate",
                "target_problem": "dynamic prompt prefix",
                "expected_effect": "improve cache stability",
            },
            "full_omc_error_propagation_audit_patch_candidate": {
                "candidate_name": "full_omc_error_propagation_audit_patch_candidate",
                "target_problem": "truncated omc errors",
                "expected_effect": "improve adaptation",
            },
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _substrate_row(task_id: str, family_id: str, template: str, source_id: str = "source_a") -> dict:
    return {
        "task_id": task_id,
        "source_id": source_id,
        "source_record_id": f"{task_id}_record",
        "family_id": family_id,
        "workflow_task_template_id": template,
        "complexity_tier": "medium",
        "real_origin_authenticity_audit": {
            "source_provenance": f"{task_id}_prov",
            "source_origin_class": "real_origin",
            "real_origin_distance": "near",
            "workflow_legitimacy_pass": True,
            "real_origin_authenticity_pass": True,
            "real_origin_authenticity_audit_pass": True,
        },
        "anti_proxy_leakage_audit": {
            "proxy_leakage_risk_present": False,
            "proxy_leakage_risk_level": "low",
            "anti_proxy_leakage_audit_pass": True,
        },
        "real_origin_substrate_admission_pass": True,
        "real_origin_substrate_inclusion_reason": "upstream_mainline_real_origin_row_preserved",
    }


def _write_v103_builder(path: Path) -> None:
    rows = [
        _substrate_row("case_goal", "control_library_maintenance", "restore_controller_assertion_behavior", "buildings"),
        _substrate_row("case_protocol", "conversion_compatibility_maintenance", "restore_conversion_compatibility", "msl"),
        _substrate_row("case_error", "multibody_constraint_maintenance", "restore_multibody_constraint_behavior", "msl"),
        _substrate_row("case_extra", "fluid_package_compatibility_maintenance", "restore_fluid_package_compatibility", "ibpsa"),
    ]
    payload = {
        "real_origin_substrate_candidate_table": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV111ProductGapPatchPackFlowTests(unittest.TestCase):
    def _write_upstream_inputs(self, root: Path, *, next_handoff: str = "execute_first_product_gap_patch_pack") -> tuple[Path, Path, Path]:
        v110_closeout = root / "v110" / "closeout.json"
        v110_governance = root / "v110" / "governance.json"
        v103_builder = root / "v103" / "builder.json"
        _write_v110_closeout(v110_closeout, next_handoff=next_handoff)
        _write_v110_governance_pack(v110_governance)
        _write_v103_builder(v103_builder)
        return v110_closeout, v110_governance, v103_builder

    def test_handoff_integrity_passes_on_ready_v110_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v110_closeout, _v110_governance, _v103_builder = self._write_upstream_inputs(root)
            payload = build_v111_handoff_integrity(
                v110_closeout_path=str(v110_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_fails_on_wrong_handoff_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v110_closeout, _v110_governance, _v103_builder = self._write_upstream_inputs(
                root,
                next_handoff="freeze_first_product_gap_evaluation_substrate",
            )
            payload = build_v111_handoff_integrity(
                v110_closeout_path=str(v110_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_patch_pack_execution_ready_on_current_mainline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _v110_closeout, v110_governance, _v103_builder = self._write_upstream_inputs(root)
            payload = build_v111_patch_pack_execution(
                v110_governance_pack_path=str(v110_governance),
                out_dir=str(root / "patch"),
            )
            self.assertEqual(payload["patch_pack_execution_status"], "ready")
            self.assertEqual(payload["partial_row_count"], 0)

    def test_bounded_validation_pack_preserves_traceability_to_v103_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _v110_closeout, _v110_governance, v103_builder = self._write_upstream_inputs(root)
            payload = build_v111_bounded_validation_pack(
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "validation"),
            )
            self.assertEqual(payload["validation_pack_status"], "ready")
            self.assertTrue(payload["one_to_one_traceability_pass"])
            self.assertEqual(payload["validation_case_ids"], ["case_goal", "case_protocol", "case_error"])

    def test_closeout_routes_to_ready_when_patch_pack_and_validation_are_complete(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v110_closeout, v110_governance, v103_builder = self._write_upstream_inputs(root)
            payload = build_v111_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                patch_pack_execution_path=str(root / "patch" / "summary.json"),
                bounded_validation_pack_path=str(root / "validation" / "summary.json"),
                v110_closeout_path=str(v110_closeout),
                v110_governance_pack_path=str(v110_governance),
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_1_first_product_gap_patch_pack_ready")
            self.assertEqual(payload["conclusion"]["v0_11_2_handoff_mode"], "freeze_first_product_gap_evaluation_substrate")

    def test_closeout_routes_to_partial_when_required_sidecar_field_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v110_closeout, v110_governance, v103_builder = self._write_upstream_inputs(root)
            build_v111_handoff_integrity(
                v110_closeout_path=str(v110_closeout),
                out_dir=str(root / "handoff"),
            )
            build_v111_patch_pack_execution(
                v110_governance_pack_path=str(v110_governance),
                out_dir=str(root / "patch"),
            )
            validation = build_v111_bounded_validation_pack(
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "validation"),
            )
            validation["required_sidecar_fields_emitted"] = False
            validation["validation_pack_status"] = "partial"
            (root / "validation" / "summary.json").write_text(json.dumps(validation), encoding="utf-8")
            payload = build_v111_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                patch_pack_execution_path=str(root / "patch" / "summary.json"),
                bounded_validation_pack_path=str(root / "validation" / "summary.json"),
                v110_closeout_path=str(v110_closeout),
                v110_governance_pack_path=str(v110_governance),
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_1_first_product_gap_patch_pack_partial")
            self.assertEqual(payload["conclusion"]["v0_11_2_handoff_mode"], "finish_patch_pack_or_sidecar_observability_first")

    def test_closeout_routes_to_invalid_on_bad_v110_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v110_closeout, v110_governance, v103_builder = self._write_upstream_inputs(
                root,
                next_handoff="freeze_first_product_gap_evaluation_substrate",
            )
            payload = build_v111_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                patch_pack_execution_path=str(root / "patch" / "summary.json"),
                bounded_validation_pack_path=str(root / "validation" / "summary.json"),
                v110_closeout_path=str(v110_closeout),
                v110_governance_pack_path=str(v110_governance),
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_1_patch_pack_inputs_invalid")

    def test_patch_pack_execution_can_drop_to_partial_when_runtime_wiring_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _v110_closeout, v110_governance, _v103_builder = self._write_upstream_inputs(root)
            with patch(
                "gateforge.agent_modelica_v0_11_1_patch_pack_execution._load_live_executor_source",
                return_value="parser.add_argument(\"--workflow-goal\", default=\"\")\n",
            ):
                payload = build_v111_patch_pack_execution(
                    v110_governance_pack_path=str(v110_governance),
                    out_dir=str(root / "patch"),
                )
            self.assertEqual(payload["patch_pack_execution_status"], "partial")
            self.assertGreater(payload["partial_row_count"], 0)


if __name__ == "__main__":
    unittest.main()
