from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_4_3_closeout import build_v043_closeout
from gateforge.agent_modelica_v0_4_3_dispatch_audit import build_v043_dispatch_audit
from gateforge.agent_modelica_v0_4_3_real_backcheck import build_v043_real_backcheck
from gateforge.agent_modelica_v0_4_3_real_slice_freeze import build_v043_real_slice_freeze
from gateforge.agent_modelica_v0_4_3_v0_4_4_handoff import build_v043_v0_4_4_handoff


class AgentModelicaV043RealBackcheckFlowTests(unittest.TestCase):
    def _write_generation_census(self, path: Path) -> None:
        rows = []
        tasks = [
            ("gen_simple_rc_lowpass_filter", "simple"),
            ("gen_medium_dc_motor_pi_speed", "medium"),
            ("gen_medium_two_room_thermal_control", "medium"),
            ("gen_medium_rlc_sensor_feedback", "medium"),
            ("gen_complex_liquid_cooling_loop", "complex"),
            ("gen_complex_hydronic_heating_loop", "complex"),
            ("gen_complex_building_hvac_zone", "complex"),
            ("gen_complex_heat_pump_buffer_tank_loop", "complex"),
        ]
        for task_id, tier in tasks:
            rows.append(
                {
                    "task_id": task_id,
                    "complexity_tier": tier,
                    "first_failure": {
                        "dominant_stage_subtype": "stage_2_structural_balance_reference",
                        "error_subtype": "undefined_symbol",
                    },
                }
            )
        payload = {"rows": rows}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v042_real_backcheck(self, path: Path) -> None:
        payload = {
            "real_backcheck_task_count": 6,
            "real_gain_delta_pct": 50.0,
            "real_conditioned_signature_advance_rate_pct": 66.7,
            "real_unconditioned_success_rate_pct": 0.0,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v042_closeout(self, path: Path) -> None:
        payload = {
            "conclusion": {
                "version_decision": "v0_4_2_synthetic_gain_supported_real_backcheck_partial",
                "conditioning_gain_supported": True,
            }
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v043_reports_supported_when_widened_real_slice_stays_positive(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            generation = root / "generation" / "summary.json"
            previous_real = root / "v042" / "real.json"
            previous_closeout = root / "v042" / "closeout.json"
            self._write_generation_census(generation)
            self._write_v042_real_backcheck(previous_real)
            self._write_v042_closeout(previous_closeout)

            build_v043_real_slice_freeze(
                generation_census_path=str(generation),
                v0_4_2_real_backcheck_path=str(previous_real),
                out_dir=str(root / "freeze"),
            )
            build_v043_real_backcheck(
                real_slice_freeze_path=str(root / "freeze" / "summary.json"),
                v0_4_2_real_backcheck_path=str(previous_real),
                out_dir=str(root / "real"),
            )
            build_v043_dispatch_audit(
                real_slice_freeze_path=str(root / "freeze" / "summary.json"),
                out_dir=str(root / "dispatch"),
            )
            build_v043_v0_4_4_handoff(
                v0_4_2_closeout_path=str(previous_closeout),
                real_backcheck_path=str(root / "real" / "summary.json"),
                dispatch_audit_path=str(root / "dispatch" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            payload = build_v043_closeout(
                v0_4_2_closeout_path=str(previous_closeout),
                real_slice_freeze_path=str(root / "freeze" / "summary.json"),
                real_backcheck_path=str(root / "real" / "summary.json"),
                dispatch_audit_path=str(root / "dispatch" / "summary.json"),
                v0_4_4_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_3_real_backcheck_supported")

    def test_v043_reports_dispatch_regressed_when_policy_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            previous_closeout = root / "v042" / "closeout.json"
            self._write_v042_closeout(previous_closeout)
            (root / "freeze.json").write_text(json.dumps({"widened_real_slice_ready": True, "real_slice_task_count": 10, "real_family_coverage_breakdown": {"component_api_alignment": 3, "local_interface_alignment": 3, "medium_redeclare_alignment": 4}, "real_complexity_breakdown": {"medium": 5, "complex": 5}, "overlap_case_count": 10}), encoding="utf-8")
            (root / "real.json").write_text(json.dumps({"real_backcheck_status": "supported", "real_gain_delta_vs_v0_4_2_pct": 10.0, "real_signature_advance_delta_vs_v0_4_2_pct": 10.0}), encoding="utf-8")
            (root / "dispatch.json").write_text(json.dumps({"policy_baseline_valid": False, "policy_failure_mode": "dispatch_regression"}), encoding="utf-8")
            (root / "handoff.json").write_text(json.dumps({"v0_4_4_handoff_mode": "refine_dispatch_policy"}), encoding="utf-8")
            payload = build_v043_closeout(
                v0_4_2_closeout_path=str(previous_closeout),
                real_slice_freeze_path=str(root / "freeze.json"),
                real_backcheck_path=str(root / "real.json"),
                dispatch_audit_path=str(root / "dispatch.json"),
                v0_4_4_handoff_path=str(root / "handoff.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_3_dispatch_validity_regressed")


if __name__ == "__main__":
    unittest.main()
