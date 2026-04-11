from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_11_2_closeout import build_v112_closeout
from gateforge.agent_modelica_v0_11_2_handoff_integrity import build_v112_handoff_integrity
from gateforge.agent_modelica_v0_11_2_product_gap_substrate_admission import build_v112_product_gap_substrate_admission
from gateforge.agent_modelica_v0_11_2_product_gap_substrate_builder import build_v112_product_gap_substrate_builder


def _write_v111_closeout(path: Path, *, next_handoff: str = "freeze_first_product_gap_evaluation_substrate") -> None:
    payload = {
        "conclusion": {
            "version_decision": "v0_11_1_first_product_gap_patch_pack_ready",
            "first_product_gap_patch_pack_status": "ready",
            "v0_11_2_handoff_mode": next_handoff,
        },
        "patch_pack_execution": {
            "patch_pack_execution_status": "ready",
        },
        "bounded_validation_pack": {
            "validation_pack_status": "ready",
            "required_sidecar_fields_emitted": True,
            "one_to_one_traceability_pass": True,
            "profile_level_claim_made": False,
            "bounded_validation_only": True,
            "non_regression_pass": True,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_v103_row(index: int) -> dict:
    family_map = [
        ("control_library_maintenance", "restore_controller_assertion_behavior", "open_source_issue_archive_buildings"),
        ("conversion_compatibility_maintenance", "restore_conversion_compatibility", "open_source_issue_archive_msl"),
        ("multibody_constraint_maintenance", "restore_multibody_constraint_behavior", "open_source_issue_archive_msl"),
        ("fluid_package_compatibility_maintenance", "restore_fluid_package_compatibility", "open_source_issue_archive_ibpsa"),
    ]
    family_id, template, source_id = family_map[index % len(family_map)]
    return {
        "task_id": f"case_{index:02d}",
        "source_id": source_id,
        "source_record_id": f"record_{index:02d}",
        "family_id": family_id,
        "workflow_task_template_id": template,
        "complexity_tier": "medium",
        "real_origin_authenticity_audit": {
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
    payload = {
        "real_origin_substrate_candidate_table": [_make_v103_row(i) for i in range(12)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV112ProductGapSubstrateFlowTests(unittest.TestCase):
    def _write_upstream_inputs(self, root: Path, *, next_handoff: str = "freeze_first_product_gap_evaluation_substrate") -> tuple[Path, Path]:
        v111_closeout = root / "v111" / "closeout.json"
        v103_builder = root / "v103" / "builder.json"
        _write_v111_closeout(v111_closeout, next_handoff=next_handoff)
        _write_v103_builder(v103_builder)
        return v111_closeout, v103_builder

    def test_handoff_integrity_passes_on_ready_v111_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v111_closeout, _v103_builder = self._write_upstream_inputs(root)
            payload = build_v112_handoff_integrity(
                v111_closeout_path=str(v111_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_fails_on_wrong_handoff_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v111_closeout, _v103_builder = self._write_upstream_inputs(
                root,
                next_handoff="finish_product_gap_substrate_freeze_first",
            )
            payload = build_v112_handoff_integrity(
                v111_closeout_path=str(v111_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_same_substrate_default_path_freezes_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _v111_closeout, v103_builder = self._write_upstream_inputs(root)
            builder = build_v112_product_gap_substrate_builder(
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "builder"),
            )
            self.assertFalse(builder["derivative_used"])
            self.assertEqual(builder["product_gap_candidate_count"], 12)
            admission = build_v112_product_gap_substrate_admission(
                product_gap_substrate_builder_path=str(root / "builder" / "summary.json"),
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "admission"),
            )
            self.assertEqual(admission["product_gap_substrate_admission_status"], "ready")

    def test_closeout_routes_to_partial_when_row_lacks_required_instrumentation(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v111_closeout, v103_builder = self._write_upstream_inputs(root)
            build_v112_handoff_integrity(
                v111_closeout_path=str(v111_closeout),
                out_dir=str(root / "handoff"),
            )
            builder = build_v112_product_gap_substrate_builder(
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "builder"),
            )
            builder["product_gap_candidate_table"][0]["product_gap_context_contract_version"] = ""
            (root / "builder" / "summary.json").write_text(json.dumps(builder), encoding="utf-8")
            payload = build_v112_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                product_gap_substrate_builder_path=str(root / "builder" / "summary.json"),
                product_gap_substrate_admission_path=str(root / "admission" / "summary.json"),
                v111_closeout_path=str(v111_closeout),
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_2_first_product_gap_substrate_partial")

    def test_closeout_routes_to_invalid_on_silent_resampling_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v111_closeout, v103_builder = self._write_upstream_inputs(root)
            build_v112_handoff_integrity(
                v111_closeout_path=str(v111_closeout),
                out_dir=str(root / "handoff"),
            )
            build_v112_product_gap_substrate_builder(
                v103_substrate_builder_path=str(v103_builder),
                derivative_used=True,
                named_product_boundary_reason="instrumentation_only_transformation",
                added_case_rows=[{"task_id": "foreign_case"}],
                out_dir=str(root / "builder"),
            )
            payload = build_v112_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                product_gap_substrate_builder_path=str(root / "builder" / "summary.json"),
                product_gap_substrate_admission_path=str(root / "admission" / "summary.json"),
                v111_closeout_path=str(v111_closeout),
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_2_product_gap_substrate_inputs_invalid")

    def test_default_path_keeps_product_gap_substrate_size_twelve(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _v111_closeout, v103_builder = self._write_upstream_inputs(root)
            builder = build_v112_product_gap_substrate_builder(
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "builder"),
            )
            self.assertEqual(builder["product_gap_candidate_count"], 12)

    def test_derivative_without_named_allowed_reason_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _v111_closeout, v103_builder = self._write_upstream_inputs(root)
            builder = build_v112_product_gap_substrate_builder(
                v103_substrate_builder_path=str(v103_builder),
                derivative_used=True,
                named_product_boundary_reason="",
                removed_case_ids=["case_11"],
                out_dir=str(root / "builder"),
            )
            self.assertEqual(builder["derivative_rule_status"], "invalid")
            admission = build_v112_product_gap_substrate_admission(
                product_gap_substrate_builder_path=str(root / "builder" / "summary.json"),
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "admission"),
            )
            self.assertEqual(admission["product_gap_substrate_admission_status"], "invalid")

    def test_valid_derivative_with_named_reason_routes_to_partial_not_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v111_closeout, v103_builder = self._write_upstream_inputs(root)
            build_v112_handoff_integrity(
                v111_closeout_path=str(v111_closeout),
                out_dir=str(root / "handoff"),
            )
            build_v112_product_gap_substrate_builder(
                v103_substrate_builder_path=str(v103_builder),
                derivative_used=True,
                named_product_boundary_reason="protocol_scope_incompatibility",
                removed_case_ids=["case_11"],
                out_dir=str(root / "builder"),
            )
            payload = build_v112_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                product_gap_substrate_builder_path=str(root / "builder" / "summary.json"),
                product_gap_substrate_admission_path=str(root / "admission" / "summary.json"),
                v111_closeout_path=str(v111_closeout),
                v103_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_2_first_product_gap_substrate_partial")


if __name__ == "__main__":
    unittest.main()
