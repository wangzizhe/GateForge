from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_18_closeout import build_v0318_closeout
from gateforge.agent_modelica_v0_3_18_stage2_characterization import build_stage2_characterization
from gateforge.agent_modelica_v0_3_18_stage2_diagnosis import build_stage2_diagnosis
from gateforge.agent_modelica_v0_3_18_stage2_sample_manifest import build_stage2_sample_manifest


SELECTED = [
    ("gen_simple_rc_lowpass_filter", "simple", 1, "undefined_symbol"),
    ("gen_simple_thermal_heated_mass", "simple", 2, "undefined_symbol"),
    ("gen_simple_two_inertia_shaft", "simple", 3, "underconstrained_system"),
    ("gen_simple_sine_driven_mass", "simple", 4, "undefined_symbol"),
    ("gen_medium_dc_motor_pi_speed", "medium", 1, "undefined_symbol"),
    ("gen_medium_pump_tank_pipe_loop", "medium", 6, "compile_failure_unknown"),
    ("gen_complex_liquid_cooling_loop", "complex", 1, "undefined_symbol"),
    ("gen_complex_coupled_motor_drive_cooling", "complex", 6, "compile_failure_unknown"),
]


class AgentModelicaV0318Stage2AuditFlowTests(unittest.TestCase):
    def _build_fixture_inputs(self, root: Path) -> tuple[Path, Path, Path, Path]:
        prompt_tasks = []
        census_rows = []
        repair_tasks = []
        one_step_rows = []
        result_dir = root / "results"
        for task_id, tier, ordinal, subtype in SELECTED:
            prompt_tasks.append(
                {
                    "task_id": task_id,
                    "role": "active",
                    "ordinal_within_tier": ordinal,
                    "complexity_tier": tier,
                    "model_name": f"{task_id}_Model",
                    "natural_language_spec": f"Spec for {task_id}",
                    "expected_domain_tags": ["fixture"],
                    "expected_component_count_band": "3-5",
                    "allowed_library_scope": "MSL only",
                }
            )
            first_failure = {
                "round_idx": 1,
                "dominant_stage_subtype": "stage_2_structural_balance_reference",
                "error_subtype": subtype,
                "observed_failure_type": "model_check_error",
                "reason": "model check failed" if subtype != "underconstrained_system" else "structural balance failed",
                "residual_signal_cluster": f"stage_2_structural_balance_reference|{subtype}",
            }
            census_rows.append(
                {
                    "task_id": task_id,
                    "complexity_tier": tier,
                    "role": "active",
                    "ordinal_within_tier": ordinal,
                    "model_name": f"{task_id}_Model",
                    "natural_language_spec": f"Spec for {task_id}",
                    "expected_domain_tags": ["fixture"],
                    "expected_component_count_band": "3-5",
                    "allowed_library_scope": "MSL only",
                }
            )
            repair_tasks.append(
                {
                    "task_id": task_id,
                    "complexity_tier": tier,
                    "source_model_text": f"model {task_id}_Model\nend {task_id}_Model;",
                    "mutated_model_text": f"model {task_id}_Model\nend {task_id}_Model;",
                    "first_failure": first_failure,
                    "result_json_path": str((result_dir / f"{task_id}.json").resolve()),
                }
            )
            result_payload = {
                "attempts": [
                    {
                        "round": 1,
                        "log_excerpt": f"compiler output for {task_id}",
                    }
                ]
            }
            (result_dir).mkdir(parents=True, exist_ok=True)
            (result_dir / f"{task_id}.json").write_text(json.dumps(result_payload), encoding="utf-8")
            one_step_rows.append(
                {
                    "task_id": task_id,
                    "complexity_tier": tier,
                    "result_json_path": str((result_dir / f"{task_id}.json").resolve()),
                    "repair_action_type": "llm_repair",
                    "second_residual": {
                        "round_idx": 2,
                        "dominant_stage_subtype": "stage_2_structural_balance_reference",
                        "error_subtype": subtype,
                        "observed_failure_type": "model_check_error",
                        "reason": "model check failed",
                        "residual_signal_cluster": f"stage_2_structural_balance_reference|{subtype}",
                    },
                    "second_residual_actionability": "low_actionability",
                }
            )

        prompt_pack_path = root / "prompt_pack.json"
        generation_census_path = root / "generation_census.json"
        repair_taskset_path = root / "repair_taskset.json"
        one_step_path = root / "one_step.json"
        prompt_pack_path.write_text(json.dumps({"tasks": prompt_tasks}), encoding="utf-8")
        generation_census_path.write_text(json.dumps({"rows": census_rows}), encoding="utf-8")
        repair_taskset_path.write_text(json.dumps({"tasks": repair_tasks}), encoding="utf-8")
        one_step_path.write_text(json.dumps({"rows": one_step_rows}), encoding="utf-8")
        return prompt_pack_path, generation_census_path, repair_taskset_path, one_step_path

    def test_sample_manifest_freezes_expected_task_ids(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prompt_pack_path, generation_census_path, repair_taskset_path, one_step_path = self._build_fixture_inputs(root)
            payload = build_stage2_sample_manifest(
                prompt_pack_path=str(prompt_pack_path),
                generation_census_path=str(generation_census_path),
                repair_taskset_path=str(repair_taskset_path),
                one_step_repair_path=str(one_step_path),
                out_dir=str(root / "manifest"),
            )
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("sample_count"), 8)
            self.assertEqual(payload.get("tier_counts"), {"simple": 4, "medium": 2, "complex": 2})

    def test_diagnosis_and_characterization_produce_partial_repairability(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prompt_pack_path, generation_census_path, repair_taskset_path, one_step_path = self._build_fixture_inputs(root)
            manifest = build_stage2_sample_manifest(
                prompt_pack_path=str(prompt_pack_path),
                generation_census_path=str(generation_census_path),
                repair_taskset_path=str(repair_taskset_path),
                one_step_repair_path=str(one_step_path),
                out_dir=str(root / "manifest"),
            )
            diagnosis = build_stage2_diagnosis(
                sample_manifest_path=str(root / "manifest" / "manifest.json"),
                out_dir=str(root / "diagnosis"),
            )
            self.assertEqual(diagnosis.get("status"), "PASS")
            self.assertEqual(diagnosis.get("authority_confirmation_status"), "PENDING_USER_CONFIRMATION")
            characterization = build_stage2_characterization(
                diagnosis_path=str(root / "diagnosis" / "records.json"),
                out_dir=str(root / "characterization"),
            )
            self.assertEqual(characterization.get("status"), "PASS")
            self.assertEqual(characterization.get("provisional_version_decision"), "stage_2_partially_repairable")
            self.assertEqual(characterization.get("dominant_target_action_type"), "component_api_alignment")

    def test_closeout_stays_draft_until_human_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prompt_pack_path, generation_census_path, repair_taskset_path, one_step_path = self._build_fixture_inputs(root)
            build_stage2_sample_manifest(
                prompt_pack_path=str(prompt_pack_path),
                generation_census_path=str(generation_census_path),
                repair_taskset_path=str(repair_taskset_path),
                one_step_repair_path=str(one_step_path),
                out_dir=str(root / "manifest"),
            )
            build_stage2_diagnosis(
                sample_manifest_path=str(root / "manifest" / "manifest.json"),
                out_dir=str(root / "diagnosis"),
            )
            build_stage2_characterization(
                diagnosis_path=str(root / "diagnosis" / "records.json"),
                out_dir=str(root / "characterization"),
            )
            payload = build_v0318_closeout(
                sample_manifest_path=str(root / "manifest" / "manifest.json"),
                diagnosis_path=str(root / "diagnosis" / "records.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                targeting_path=str(root / "targeting" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload.get("closeout_status"), "STAGE2_ACTIONABILITY_AUDIT_DRAFT_READY")
            self.assertEqual(payload.get("authority_confirmation_status"), "PENDING_USER_CONFIRMATION")

    def test_confirmed_diagnosis_promotes_closeout_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prompt_pack_path, generation_census_path, repair_taskset_path, one_step_path = self._build_fixture_inputs(root)
            build_stage2_sample_manifest(
                prompt_pack_path=str(prompt_pack_path),
                generation_census_path=str(generation_census_path),
                repair_taskset_path=str(repair_taskset_path),
                one_step_repair_path=str(one_step_path),
                out_dir=str(root / "manifest"),
            )
            build_stage2_diagnosis(
                sample_manifest_path=str(root / "manifest" / "manifest.json"),
                authority_confirmation_status="CONFIRMED_USER",
                out_dir=str(root / "diagnosis"),
            )
            build_stage2_characterization(
                diagnosis_path=str(root / "diagnosis" / "records.json"),
                out_dir=str(root / "characterization"),
            )
            payload = build_v0318_closeout(
                sample_manifest_path=str(root / "manifest" / "manifest.json"),
                diagnosis_path=str(root / "diagnosis" / "records.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                targeting_path=str(root / "targeting" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload.get("closeout_status"), "STAGE2_ACTIONABILITY_AUDIT_READY")
            self.assertEqual(payload.get("authority_confirmation_status"), "CONFIRMED_USER")


if __name__ == "__main__":
    unittest.main()
