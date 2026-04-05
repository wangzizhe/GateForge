from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_4_4_authority_dispatch_audit import build_v044_authority_dispatch_audit
from gateforge.agent_modelica_v0_4_4_authority_slice_freeze import build_v044_authority_slice_freeze
from gateforge.agent_modelica_v0_4_4_closeout import build_v044_closeout
from gateforge.agent_modelica_v0_4_4_promotion_adjudication import build_v044_promotion_adjudication
from gateforge.agent_modelica_v0_4_4_real_authority_recheck import build_v044_real_authority_recheck
from gateforge.agent_modelica_v0_4_4_v0_4_5_handoff import build_v044_v0_4_5_handoff


class AgentModelicaV044RealAuthorityFlowTests(unittest.TestCase):
    def _write_v043_real_slice(self, path: Path) -> None:
        tasks = [
            ("gen_simple_rc_lowpass_filter", "component_api_alignment", "simple"),
            ("gen_simple_thermal_heated_mass", "component_api_alignment", "simple"),
            ("gen_simple_sine_driven_mass", "component_api_alignment", "simple"),
            ("gen_medium_dc_motor_pi_speed", "component_api_alignment", "medium"),
            ("gen_medium_mass_spring_position_control", "component_api_alignment", "medium"),
            ("gen_medium_battery_load_converter", "component_api_alignment", "medium"),
            ("gen_medium_two_room_thermal_control", "local_interface_alignment", "medium"),
            ("gen_medium_two_tank_level_control", "local_interface_alignment", "medium"),
            ("gen_medium_rlc_sensor_feedback", "local_interface_alignment", "medium"),
            ("gen_medium_motor_thermal_protection", "local_interface_alignment", "medium"),
            ("gen_complex_building_hvac_zone", "local_interface_alignment", "complex"),
            ("gen_complex_ev_thermal_management", "local_interface_alignment", "complex"),
            ("gen_complex_liquid_cooling_loop", "medium_redeclare_alignment", "complex"),
            ("gen_complex_hydronic_heating_loop", "medium_redeclare_alignment", "complex"),
            ("gen_complex_multi_tank_heat_exchange", "medium_redeclare_alignment", "complex"),
            ("gen_complex_chilled_water_distribution", "medium_redeclare_alignment", "complex"),
            ("gen_complex_heat_pump_buffer_tank_loop", "medium_redeclare_alignment", "complex"),
            ("gen_complex_solar_thermal_storage_loop", "medium_redeclare_alignment", "complex"),
        ]
        payload = {
            "real_slice_task_count": len(tasks),
            "real_complexity_breakdown": {"simple": 3, "medium": 7, "complex": 8},
            "task_rows": [
                {"task_id": task_id, "family_id": family_id, "complexity_tier": tier}
                for task_id, family_id, tier in tasks
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v043_real_backcheck(self, path: Path) -> None:
        payload = {
            "real_gain_delta_pct": 77.8,
            "real_signature_advance_delta_pct": 88.9,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v042_closeout(self, path: Path) -> None:
        payload = {"conclusion": {"conditioning_gain_supported": True}}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v043_closeout(self, path: Path) -> None:
        payload = {"conclusion": {"version_decision": "v0_4_3_real_backcheck_supported"}}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v044_promotes_real_authority_on_harder_slice(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v043_real_slice(root / "v043" / "real_slice.json")
            self._write_v043_real_backcheck(root / "v043" / "real_backcheck.json")
            self._write_v042_closeout(root / "v042" / "closeout.json")
            self._write_v043_closeout(root / "v043" / "closeout.json")

            build_v044_authority_slice_freeze(
                v0_4_3_real_slice_freeze_path=str(root / "v043" / "real_slice.json"),
                out_dir=str(root / "freeze"),
            )
            build_v044_real_authority_recheck(
                authority_slice_freeze_path=str(root / "freeze" / "summary.json"),
                v0_4_3_real_backcheck_path=str(root / "v043" / "real_backcheck.json"),
                out_dir=str(root / "recheck"),
            )
            build_v044_authority_dispatch_audit(
                authority_slice_freeze_path=str(root / "freeze" / "summary.json"),
                out_dir=str(root / "dispatch"),
            )
            build_v044_promotion_adjudication(
                v0_4_3_real_slice_freeze_path=str(root / "v043" / "real_slice.json"),
                authority_slice_freeze_path=str(root / "freeze" / "summary.json"),
                real_authority_recheck_path=str(root / "recheck" / "summary.json"),
                authority_dispatch_audit_path=str(root / "dispatch" / "summary.json"),
                out_dir=str(root / "promotion"),
            )
            build_v044_v0_4_5_handoff(
                promotion_adjudication_path=str(root / "promotion" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            payload = build_v044_closeout(
                v0_4_2_closeout_path=str(root / "v042" / "closeout.json"),
                v0_4_3_closeout_path=str(root / "v043" / "closeout.json"),
                authority_slice_freeze_path=str(root / "freeze" / "summary.json"),
                real_authority_recheck_path=str(root / "recheck" / "summary.json"),
                authority_dispatch_audit_path=str(root / "dispatch" / "summary.json"),
                promotion_adjudication_path=str(root / "promotion" / "summary.json"),
                v0_4_5_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_4_real_authority_promoted")

    def test_v044_reports_policy_regressed_when_dispatch_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v042_closeout(root / "v042" / "closeout.json")
            self._write_v043_closeout(root / "v043" / "closeout.json")
            (root / "freeze.json").write_text(json.dumps({"authority_slice_ready": True}), encoding="utf-8")
            (root / "recheck.json").write_text(json.dumps({"real_authority_recheck_status": "supported", "real_gain_delta_pct": 10.0, "real_signature_advance_delta_pct": 10.0}), encoding="utf-8")
            (root / "dispatch.json").write_text(json.dumps({"policy_baseline_valid": False, "policy_failure_mode": "authority_dispatch_ambiguity"}), encoding="utf-8")
            (root / "promotion.json").write_text(json.dumps({"real_authority_upgrade_supported": False, "promotion_basis": "none"}), encoding="utf-8")
            (root / "handoff.json").write_text(json.dumps({"v0_4_5_handoff_mode": "strengthen_dispatch_policy_authority"}), encoding="utf-8")
            payload = build_v044_closeout(
                v0_4_2_closeout_path=str(root / "v042" / "closeout.json"),
                v0_4_3_closeout_path=str(root / "v043" / "closeout.json"),
                authority_slice_freeze_path=str(root / "freeze.json"),
                real_authority_recheck_path=str(root / "recheck.json"),
                authority_dispatch_audit_path=str(root / "dispatch.json"),
                promotion_adjudication_path=str(root / "promotion.json"),
                v0_4_5_handoff_path=str(root / "handoff.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_4_policy_validity_regressed")


if __name__ == "__main__":
    unittest.main()
