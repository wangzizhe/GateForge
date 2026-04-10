from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_v0_10_4_closeout import build_v104_closeout
from gateforge.agent_modelica_v0_10_4_handoff_integrity import build_v104_handoff_integrity
from gateforge.agent_modelica_v0_10_4_real_origin_profile_replay_pack import (
    _replay_real_origin_substrate_run as replay_real_origin_substrate_run,
)
from gateforge.agent_modelica_v0_10_4_real_origin_profile_replay_pack import build_v104_real_origin_profile_replay_pack


def _substrate_row(
    task_id: str,
    source_id: str,
    family: str,
    complexity: str,
    template: str,
    *,
    distance: str = "near",
) -> dict:
    return {
        "task_id": task_id,
        "source_id": source_id,
        "source_record_id": f"{task_id}_record",
        "family_id": family,
        "workflow_task_template_id": template,
        "complexity_tier": complexity,
        "real_origin_authenticity_audit": {
            "source_provenance": f"{task_id}_prov",
            "source_origin_class": "real_origin",
            "real_origin_distance": distance,
            "workflow_legitimacy_pass": True,
            "real_origin_authenticity_pass": True,
            "real_origin_authenticity_audit_pass": True,
        },
        "anti_proxy_leakage_audit": {
            "proxy_leakage_risk_present": distance == "medium",
            "proxy_leakage_risk_level": "medium" if distance == "medium" else "low",
            "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "Fixture row.",
            "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
            "anti_proxy_leakage_audit_pass": True,
        },
        "real_origin_substrate_admission_pass": True,
        "real_origin_substrate_inclusion_reason": "upstream_mainline_real_origin_row_preserved",
    }


def _write_v103_closeout(path: Path, *, version_decision: str = "v0_10_3_first_real_origin_workflow_substrate_ready") -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "real_origin_substrate_size": 12,
            "source_coverage_table": {
                "open_source_issue_archive_aixlib": 4,
                "open_source_issue_archive_buildings": 2,
                "open_source_issue_archive_ibpsa": 2,
                "open_source_issue_archive_msl": 4,
            },
            "max_single_source_share_pct": 33.3,
            "real_origin_substrate_admission_status": "ready",
            "v0_10_4_handoff_mode": "characterize_first_real_origin_workflow_profile",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v103_builder(path: Path) -> None:
    rows = [
        _substrate_row("b1", "open_source_issue_archive_buildings", "control_library_maintenance", "medium", "restore_controller_assertion_behavior"),
        _substrate_row("b2", "open_source_issue_archive_buildings", "controller_reset_maintenance", "medium", "restore_controller_reset_chain"),
        _substrate_row("m1", "open_source_issue_archive_msl", "multibody_constraint_maintenance", "complex", "restore_multibody_constraint_behavior", distance="medium"),
        _substrate_row("m2", "open_source_issue_archive_msl", "conversion_compatibility_maintenance", "simple", "restore_conversion_compatibility", distance="medium"),
        _substrate_row("m3", "open_source_issue_archive_msl", "conversion_compatibility_maintenance", "simple", "restore_conversion_compatibility", distance="medium"),
        _substrate_row("m4", "open_source_issue_archive_msl", "conversion_compatibility_maintenance", "simple", "restore_conversion_compatibility", distance="medium"),
        _substrate_row("a1", "open_source_issue_archive_aixlib", "refrigerant_interface_maintenance", "complex", "restore_refrigerant_interface_record", distance="medium"),
        _substrate_row("a2", "open_source_issue_archive_aixlib", "refrigerant_validation_maintenance", "complex", "restore_refrigerant_validation_chain", distance="medium"),
        _substrate_row("a3", "open_source_issue_archive_aixlib", "refrigerant_validation_maintenance", "medium", "restore_refrigerant_formula_example_chain", distance="medium"),
        _substrate_row("a4", "open_source_issue_archive_aixlib", "interface_compatibility_maintenance", "medium", "restore_interface_name_compatibility"),
        _substrate_row("i1", "open_source_issue_archive_ibpsa", "media_record_maintenance", "complex", "restore_media_record_consistency", distance="medium"),
        _substrate_row("i2", "open_source_issue_archive_ibpsa", "fluid_package_compatibility_maintenance", "medium", "restore_fluid_package_compatibility"),
    ]
    payload = {
        "real_origin_substrate_candidate_count": len(rows),
        "real_origin_substrate_candidate_table": rows,
        "source_mix": {
            "open_source_issue_archive_aixlib": 4,
            "open_source_issue_archive_buildings": 2,
            "open_source_issue_archive_ibpsa": 2,
            "open_source_issue_archive_msl": 4,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV104RealOriginProfileFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v103_ready_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103_closeout = root / "v103" / "closeout.json"
            v103_builder = root / "v103" / "builder.json"
            _write_v103_closeout(v103_closeout)
            _write_v103_builder(v103_builder)
            payload = build_v104_handoff_integrity(
                v103_closeout_path=str(v103_closeout),
                v103_real_origin_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_closeout_routes_to_characterized_on_stable_real_origin_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103_closeout = root / "v103" / "closeout.json"
            v103_builder = root / "v103" / "builder.json"
            _write_v103_closeout(v103_closeout)
            _write_v103_builder(v103_builder)
            payload = build_v104_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v103_closeout_path=str(v103_closeout),
                v103_real_origin_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_4_first_real_origin_workflow_profile_characterized")
            self.assertEqual(payload["conclusion"]["v0_10_5_handoff_mode"], "freeze_first_real_origin_workflow_thresholds")

    def test_closeout_routes_to_partial_when_replay_pack_has_two_flips(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103_closeout = root / "v103" / "closeout.json"
            v103_builder = root / "v103" / "builder.json"
            _write_v103_closeout(v103_closeout)
            _write_v103_builder(v103_builder)

            def _patched_replay(substrate_rows: list[dict], *, run_index: int) -> dict:
                payload = replay_real_origin_substrate_run(substrate_rows, run_index=run_index)
                if run_index == 2:
                    payload["case_result_table"][0]["pilot_outcome"] = "surface_fix_only"
                    payload["case_result_table"][0]["primary_non_success_label"] = "artifact_gap_after_surface_fix"
                    payload["case_result_table"][1]["pilot_outcome"] = "unresolved"
                    payload["case_result_table"][1]["primary_non_success_label"] = "extractive_conversion_chain_unresolved"
                return payload

            with patch("gateforge.agent_modelica_v0_10_4_real_origin_profile_replay_pack._replay_real_origin_substrate_run", side_effect=_patched_replay):
                payload = build_v104_closeout(
                    handoff_integrity_path=str(root / "handoff" / "summary.json"),
                    replay_pack_path=str(root / "replay" / "summary.json"),
                    characterization_path=str(root / "characterization" / "summary.json"),
                    v103_closeout_path=str(v103_closeout),
                    v103_real_origin_substrate_builder_path=str(v103_builder),
                    out_dir=str(root / "closeout"),
                )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_4_first_real_origin_workflow_profile_partial")
            self.assertEqual(payload["real_origin_profile_replay_pack"]["unexplained_case_flip_count"], 2)

    def test_closeout_returns_invalid_when_upstream_ready_handoff_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103_closeout = root / "v103" / "closeout.json"
            v103_builder = root / "v103" / "builder.json"
            _write_v103_closeout(v103_closeout, version_decision="v0_10_3_real_origin_substrate_inputs_invalid")
            _write_v103_builder(v103_builder)
            payload = build_v104_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v103_closeout_path=str(v103_closeout),
                v103_real_origin_substrate_builder_path=str(v103_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_4_real_origin_profile_inputs_invalid")

    def test_replay_pack_exercises_flip_detection_logic(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103_builder = root / "v103" / "builder.json"
            _write_v103_builder(v103_builder)

            def _patched_replay(substrate_rows: list[dict], *, run_index: int) -> dict:
                payload = replay_real_origin_substrate_run(substrate_rows, run_index=run_index)
                if run_index == 3:
                    payload["case_result_table"][2]["pilot_outcome"] = "surface_fix_only"
                    payload["case_result_table"][2]["primary_non_success_label"] = "artifact_gap_after_surface_fix"
                return payload

            with patch("gateforge.agent_modelica_v0_10_4_real_origin_profile_replay_pack._replay_real_origin_substrate_run", side_effect=_patched_replay):
                payload = build_v104_real_origin_profile_replay_pack(
                    v103_real_origin_substrate_builder_path=str(v103_builder),
                    out_dir=str(root / "replay"),
                )
            self.assertEqual(payload["unexplained_case_flip_count"], 1)


if __name__ == "__main__":
    unittest.main()
