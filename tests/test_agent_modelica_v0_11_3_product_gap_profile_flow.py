from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_v0_11_3_closeout import build_v113_closeout
from gateforge.agent_modelica_v0_11_3_handoff_integrity import build_v113_handoff_integrity
from gateforge.agent_modelica_v0_11_3_product_gap_profile_replay_pack import (
    _replay_product_gap_substrate_run as replay_product_gap_substrate_run,
)
from gateforge.agent_modelica_v0_11_3_product_gap_profile_replay_pack import build_v113_product_gap_profile_replay_pack


def _write_v112_closeout(path: Path, *, next_handoff: str = "characterize_first_product_gap_profile") -> None:
    payload = {
        "conclusion": {
            "version_decision": "v0_11_2_first_product_gap_substrate_ready",
            "first_product_gap_substrate_status": "ready",
            "v0_11_3_handoff_mode": next_handoff,
        },
        "product_gap_substrate_admission": {
            "product_gap_substrate_admission_status": "ready",
            "product_gap_substrate_size": 12,
            "same_substrate_continuity_pass": True,
            "instrumentation_completeness_pass": True,
            "traceability_pass": True,
            "dynamic_prompt_field_audit_state": "explicit_and_still_open",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_v112_row(index: int) -> dict:
    family_map = [
        ("control_library_maintenance", "restore_controller_assertion_behavior", "buildings", "medium"),
        ("controller_reset_maintenance", "restore_controller_reset_chain", "buildings", "medium"),
        ("multibody_constraint_maintenance", "restore_multibody_constraint_behavior", "msl", "complex"),
        ("conversion_compatibility_maintenance", "restore_conversion_compatibility", "msl", "simple"),
        ("refrigerant_interface_maintenance", "restore_refrigerant_interface_record", "aixlib", "complex"),
        ("refrigerant_validation_maintenance", "restore_refrigerant_validation_chain", "aixlib", "complex"),
        ("media_record_maintenance", "restore_media_record_consistency", "ibpsa", "complex"),
        ("fluid_package_compatibility_maintenance", "restore_fluid_package_compatibility", "ibpsa", "medium"),
        ("interface_compatibility_maintenance", "restore_interface_name_compatibility", "aixlib", "medium"),
    ]
    family_id, template, source_stub, complexity = family_map[index % len(family_map)]
    return {
        "task_id": f"case_{index:02d}",
        "source_id": f"open_source_issue_archive_{source_stub}",
        "source_record_id": f"record_{index:02d}",
        "family_id": family_id,
        "workflow_task_template_id": template,
        "complexity_tier": complexity,
        "carried_from_v0_10_3": True,
        "product_gap_scaffold_version": "gateforge_live_executor_v1_scaffold",
        "product_gap_protocol_contract_version": "gateforge_live_executor_v1_contract",
        "product_gap_context_contract_version": "v0_11_0_context_contract_v1",
        "product_gap_anti_reward_hacking_checklist_version": "v0_11_0_anti_reward_hacking_checklist_v1",
        "patch_pack_carried_observation_fields": {
            "workflow_goal_reanchoring_observed": "pending_profile_run",
            "dynamic_system_prompt_field_audit_result": "pending_profile_run",
            "full_omc_error_propagation_observed": "pending_profile_run",
        },
        "product_gap_row_admission_pass": True,
    }


def _write_v112_builder(path: Path) -> None:
    payload = {
        "product_gap_candidate_table": [_make_v112_row(i) for i in range(12)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV113ProductGapProfileFlowTests(unittest.TestCase):
    def _write_upstream_inputs(self, root: Path, *, next_handoff: str = "characterize_first_product_gap_profile") -> tuple[Path, Path]:
        v112_closeout = root / "v112" / "closeout.json"
        v112_builder = root / "v112" / "builder.json"
        _write_v112_closeout(v112_closeout, next_handoff=next_handoff)
        _write_v112_builder(v112_builder)
        return v112_closeout, v112_builder

    def test_handoff_integrity_passes_on_ready_v112_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v112_closeout, _v112_builder = self._write_upstream_inputs(root)
            payload = build_v113_handoff_integrity(
                v112_closeout_path=str(v112_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_fails_on_wrong_handoff_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v112_closeout, _v112_builder = self._write_upstream_inputs(
                root,
                next_handoff="freeze_first_product_gap_thresholds",
            )
            payload = build_v113_handoff_integrity(
                v112_closeout_path=str(v112_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_closeout_routes_to_characterized_on_carried_default_substrate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v112_closeout, v112_builder = self._write_upstream_inputs(root)
            payload = build_v113_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v112_closeout_path=str(v112_closeout),
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_3_first_product_gap_profile_characterized")
            self.assertEqual(payload["conclusion"]["v0_11_4_handoff_mode"], "freeze_first_product_gap_thresholds")

    def test_closeout_routes_to_partial_when_runtime_evidence_placeholders_are_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v112_closeout, v112_builder = self._write_upstream_inputs(root)
            build_v113_handoff_integrity(
                v112_closeout_path=str(v112_closeout),
                out_dir=str(root / "handoff"),
            )
            replay = build_v113_product_gap_profile_replay_pack(
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "replay"),
            )
            replay["observation_placeholder_fully_replaced"] = False
            replay["runtime_product_gap_evidence_completeness_pass"] = False
            replay["missing_runtime_product_gap_fields"] = ["workflow_goal_reanchoring_observed"]
            (root / "replay" / "summary.json").write_text(json.dumps(replay), encoding="utf-8")
            payload = build_v113_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v112_closeout_path=str(v112_closeout),
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_3_product_gap_profile_inputs_invalid")

    def test_closeout_routes_to_partial_when_non_success_explainability_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v112_closeout, v112_builder = self._write_upstream_inputs(root)
            build_v113_handoff_integrity(
                v112_closeout_path=str(v112_closeout),
                out_dir=str(root / "handoff"),
            )
            build_v113_product_gap_profile_replay_pack(
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "replay"),
            )
            payload = build_v113_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v112_closeout_path=str(v112_closeout),
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "closeout"),
            )
            characterization = payload["product_gap_profile_characterization"]
            characterization["product_gap_non_success_unclassified_count"] = 1
            characterization["candidate_dominant_gap_family_interpretability"] = "partial"
            (root / "characterization" / "summary.json").write_text(json.dumps(characterization), encoding="utf-8")
            payload = build_v113_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v112_closeout_path=str(v112_closeout),
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "closeout_retry"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_3_first_product_gap_profile_partial")

    def test_closeout_returns_invalid_when_upstream_ready_handoff_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v112_closeout, v112_builder = self._write_upstream_inputs(
                root,
                next_handoff="finish_product_gap_substrate_freeze_first",
            )
            payload = build_v113_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v112_closeout_path=str(v112_closeout),
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_3_product_gap_profile_inputs_invalid")

    def test_replay_pack_exercises_one_controlled_unexplained_flip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _v112_closeout, v112_builder = self._write_upstream_inputs(root)

            def _patched_replay(substrate_rows: list[dict], *, run_index: int) -> dict:
                payload = replay_product_gap_substrate_run(substrate_rows, run_index=run_index)
                if run_index == 3:
                    payload["case_result_table"][0]["product_gap_outcome"] = "surface_fix_only"
                    payload["case_result_table"][0]["primary_non_success_label"] = "context_reanchoring_fragility_after_surface_fix"
                    payload["case_result_table"][0]["candidate_gap_family"] = "context_discipline_gap"
                return payload

            with patch("gateforge.agent_modelica_v0_11_3_product_gap_profile_replay_pack._replay_product_gap_substrate_run", side_effect=_patched_replay):
                payload = build_v113_product_gap_profile_replay_pack(
                    v112_product_gap_substrate_builder_path=str(v112_builder),
                    out_dir=str(root / "replay"),
                )
            self.assertEqual(payload["unexplained_case_flip_count"], 1)

    def test_mixed_gap_family_is_allowed_on_partial_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v112_closeout, v112_builder = self._write_upstream_inputs(root)
            build_v113_handoff_integrity(
                v112_closeout_path=str(v112_closeout),
                out_dir=str(root / "handoff"),
            )
            build_v113_product_gap_profile_replay_pack(
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "replay"),
            )
            payload = build_v113_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v112_closeout_path=str(v112_closeout),
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "closeout"),
            )
            characterization = payload["product_gap_profile_characterization"]
            characterization["candidate_dominant_gap_family"] = "mixed_or_not_yet_resolved"
            characterization["candidate_dominant_gap_family_interpretability"] = "partial"
            characterization["why_this_gap_family_is_or_is_not_currently_dominant"] = "Mixed gap picture."
            (root / "characterization" / "summary.json").write_text(json.dumps(characterization), encoding="utf-8")
            payload = build_v113_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v112_closeout_path=str(v112_closeout),
                v112_product_gap_substrate_builder_path=str(v112_builder),
                out_dir=str(root / "closeout_retry"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_3_first_product_gap_profile_partial")


if __name__ == "__main__":
    unittest.main()
