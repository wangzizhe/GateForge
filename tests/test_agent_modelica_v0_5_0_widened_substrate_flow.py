from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_5_0_candidate_pack import build_v050_candidate_pack
from gateforge.agent_modelica_v0_5_0_closeout import build_v050_closeout
from gateforge.agent_modelica_v0_5_0_dispatch_cleanliness_audit import build_v050_dispatch_cleanliness_audit
from gateforge.agent_modelica_v0_5_0_widened_spec import build_v050_widened_spec


class AgentModelicaV050WidenedSubstrateFlowTests(unittest.TestCase):
    def _write_v043_real_slice_freeze(self, path: Path) -> None:
        rows = [
            ("gen_simple_rc_lowpass_filter", "component_api_alignment", "simple"),
            ("gen_simple_thermal_heated_mass", "component_api_alignment", "simple"),
            ("gen_simple_sine_driven_mass", "component_api_alignment", "simple"),
            ("gen_medium_dc_motor_pi_speed", "component_api_alignment", "medium"),
            ("gen_medium_two_room_thermal_control", "local_interface_alignment", "medium"),
            ("gen_medium_two_tank_level_control", "local_interface_alignment", "medium"),
            ("gen_medium_rlc_sensor_feedback", "local_interface_alignment", "medium"),
            ("gen_medium_motor_thermal_protection", "local_interface_alignment", "medium"),
            ("gen_complex_building_hvac_zone", "local_interface_alignment", "complex"),
            ("gen_complex_ev_thermal_management", "local_interface_alignment", "complex"),
            ("gen_medium_pump_tank_pipe_loop", "medium_redeclare_alignment", "medium"),
            ("gen_complex_hydronic_heating_loop", "medium_redeclare_alignment", "complex"),
            ("gen_complex_chilled_water_distribution", "medium_redeclare_alignment", "complex"),
            ("gen_complex_heat_pump_buffer_tank_loop", "medium_redeclare_alignment", "complex"),
            ("gen_complex_solar_thermal_storage_loop", "medium_redeclare_alignment", "complex"),
        ]
        task_rows = []
        for task_id, family_id, tier in rows:
            task_rows.append(
                {
                    "task_id": task_id,
                    "family_id": family_id,
                    "complexity_tier": tier,
                    "first_failure": {
                        "dominant_stage_subtype": "stage_2_structural_balance_reference",
                        "error_subtype": "undefined_symbol",
                    },
                }
            )
        payload = {
            "real_slice_task_count": len(task_rows),
            "v0_4_2_real_slice_task_count": 6,
            "task_rows": task_rows,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v046_closeout(self, path: Path) -> None:
        payload = {
            "conclusion": {
                "version_decision": "v0_4_phase_complete_prepare_v0_5",
                "phase_status": "learning_effectiveness_phase_complete",
            }
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v050_reports_ready_when_widened_pack_is_quantitative_and_qualitative(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v043 = root / "v043" / "summary.json"
            v046 = root / "v046" / "summary.json"
            self._write_v043_real_slice_freeze(v043)
            self._write_v046_closeout(v046)

            build_v050_widened_spec(
                v0_4_3_real_slice_freeze_path=str(v043),
                v0_4_6_closeout_path=str(v046),
                out_dir=str(root / "spec"),
            )
            build_v050_candidate_pack(
                widened_spec_path=str(root / "spec" / "summary.json"),
                v0_4_3_real_slice_freeze_path=str(v043),
                out_dir=str(root / "pack"),
            )
            build_v050_dispatch_cleanliness_audit(
                widened_spec_path=str(root / "spec" / "summary.json"),
                candidate_pack_path=str(root / "pack" / "summary.json"),
                out_dir=str(root / "dispatch"),
            )
            payload = build_v050_closeout(
                widened_spec_path=str(root / "spec" / "summary.json"),
                candidate_pack_path=str(root / "pack" / "summary.json"),
                dispatch_cleanliness_audit_path=str(root / "dispatch" / "summary.json"),
                boundary_gate_path=str(root / "gate" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_0_widened_real_substrate_ready")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_5_1_handoff_mode"), "run_boundary_mapping_first_on_frozen_slice")

    def test_v050_reports_partial_when_qualitative_widening_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v043 = root / "v043" / "summary.json"
            v046 = root / "v046" / "summary.json"
            self._write_v046_closeout(v046)
            rows = [
                {"task_id": f"gen_simple_api_{idx}", "family_id": "component_api_alignment", "complexity_tier": "simple"}
                for idx in range(13)
            ]
            payload = {"real_slice_task_count": len(rows), "v0_4_2_real_slice_task_count": 6, "task_rows": rows}
            v043.parent.mkdir(parents=True, exist_ok=True)
            v043.write_text(json.dumps(payload), encoding="utf-8")

            build_v050_widened_spec(
                v0_4_3_real_slice_freeze_path=str(v043),
                v0_4_6_closeout_path=str(v046),
                out_dir=str(root / "spec"),
            )
            build_v050_candidate_pack(
                widened_spec_path=str(root / "spec" / "summary.json"),
                v0_4_3_real_slice_freeze_path=str(v043),
                out_dir=str(root / "pack"),
            )
            build_v050_dispatch_cleanliness_audit(
                widened_spec_path=str(root / "spec" / "summary.json"),
                candidate_pack_path=str(root / "pack" / "summary.json"),
                out_dir=str(root / "dispatch"),
            )
            closeout = build_v050_closeout(
                widened_spec_path=str(root / "spec" / "summary.json"),
                candidate_pack_path=str(root / "pack" / "summary.json"),
                dispatch_cleanliness_audit_path=str(root / "dispatch" / "summary.json"),
                boundary_gate_path=str(root / "gate" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((closeout.get("conclusion") or {}).get("version_decision"), "v0_5_0_widened_real_substrate_partial")


if __name__ == "__main__":
    unittest.main()
