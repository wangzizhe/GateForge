from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_4_5_closeout import build_v045_closeout
from gateforge.agent_modelica_v0_4_5_policy_adjudication import build_v045_policy_adjudication
from gateforge.agent_modelica_v0_4_5_policy_cleanliness import build_v045_policy_cleanliness
from gateforge.agent_modelica_v0_4_5_policy_comparison import build_v045_policy_comparison
from gateforge.agent_modelica_v0_4_5_policy_slice_lock import build_v045_policy_slice_lock
from gateforge.agent_modelica_v0_4_5_v0_4_6_handoff import build_v045_v0_4_6_handoff


class AgentModelicaV045PolicyComparisonFlowTests(unittest.TestCase):
    def _write_v044_authority_slice(self, path: Path) -> None:
        rows = [
            {"task_id": "gen_medium_dc_motor_pi_speed", "family_id": "component_api_alignment", "complexity_tier": "medium", "authority_overlap_case": False},
            {"task_id": "gen_medium_two_room_thermal_control", "family_id": "local_interface_alignment", "complexity_tier": "medium", "authority_overlap_case": True},
            {"task_id": "gen_medium_two_tank_level_control", "family_id": "local_interface_alignment", "complexity_tier": "medium", "authority_overlap_case": True},
            {"task_id": "gen_complex_liquid_cooling_loop", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "authority_overlap_case": True},
            {"task_id": "gen_complex_building_hvac_zone", "family_id": "local_interface_alignment", "complexity_tier": "complex", "authority_overlap_case": True},
            {"task_id": "gen_complex_multi_tank_heat_exchange", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "authority_overlap_case": True},
        ]
        payload = {
            "authority_slice_ready": True,
            "real_authority_slice_task_count": len(rows),
            "real_authority_family_breakdown": {
                "component_api_alignment": 1,
                "local_interface_alignment": 3,
                "medium_redeclare_alignment": 2,
            },
            "real_authority_complexity_breakdown": {"medium": 3, "complex": 3},
            "real_authority_overlap_case_count": 5,
            "task_rows": rows,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v044_recheck(self, path: Path) -> None:
        rows = [
            {"task_id": "gen_medium_dc_motor_pi_speed", "conditioned_success": True, "conditioned_signature_advance": True},
            {"task_id": "gen_medium_two_room_thermal_control", "conditioned_success": True, "conditioned_signature_advance": True},
            {"task_id": "gen_medium_two_tank_level_control", "conditioned_success": False, "conditioned_signature_advance": True},
            {"task_id": "gen_complex_liquid_cooling_loop", "conditioned_success": True, "conditioned_signature_advance": True},
            {"task_id": "gen_complex_building_hvac_zone", "conditioned_success": True, "conditioned_signature_advance": True},
            {"task_id": "gen_complex_multi_tank_heat_exchange", "conditioned_success": True, "conditioned_signature_advance": False},
        ]
        payload = {"task_rows": rows}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_closeouts(self, v043: Path, v044: Path) -> None:
        v043.parent.mkdir(parents=True, exist_ok=True)
        v044.parent.mkdir(parents=True, exist_ok=True)
        v043.write_text(json.dumps({"conclusion": {"version_decision": "v0_4_3_real_backcheck_supported"}}), encoding="utf-8")
        v044.write_text(json.dumps({"conclusion": {"version_decision": "v0_4_4_real_authority_promoted"}}), encoding="utf-8")

    def test_v045_supports_baseline_policy_when_alternative_is_weaker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v044_authority_slice(root / "v044" / "slice.json")
            self._write_v044_recheck(root / "v044" / "recheck.json")
            self._write_closeouts(root / "v043" / "closeout.json", root / "v044" / "closeout.json")

            build_v045_policy_slice_lock(v0_4_4_authority_slice_path=str(root / "v044" / "slice.json"), out_dir=str(root / "lock"))
            build_v045_policy_comparison(policy_slice_lock_path=str(root / "lock" / "summary.json"), v0_4_4_real_recheck_path=str(root / "v044" / "recheck.json"), out_dir=str(root / "compare"))
            build_v045_policy_cleanliness(policy_comparison_path=str(root / "compare" / "summary.json"), out_dir=str(root / "clean"))
            build_v045_policy_adjudication(policy_comparison_path=str(root / "compare" / "summary.json"), policy_cleanliness_path=str(root / "clean" / "summary.json"), out_dir=str(root / "adj"))
            build_v045_v0_4_6_handoff(policy_adjudication_path=str(root / "adj" / "summary.json"), policy_cleanliness_path=str(root / "clean" / "summary.json"), out_dir=str(root / "handoff"))
            payload = build_v045_closeout(
                v0_4_3_closeout_path=str(root / "v043" / "closeout.json"),
                v0_4_4_closeout_path=str(root / "v044" / "closeout.json"),
                policy_slice_lock_path=str(root / "lock" / "summary.json"),
                policy_comparison_path=str(root / "compare" / "summary.json"),
                policy_cleanliness_path=str(root / "clean" / "summary.json"),
                policy_adjudication_path=str(root / "adj" / "summary.json"),
                v0_4_6_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_5_dispatch_policy_empirically_supported")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_4_x_next_step"), "run_v0_4_phase_synthesis")

    def test_v045_marks_invalid_when_comparison_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_closeouts(root / "v043" / "closeout.json", root / "v044" / "closeout.json")
            (root / "lock.json").write_text(json.dumps({"policy_comparison_slice_locked": True}), encoding="utf-8")
            (root / "comparison.json").write_text(json.dumps({"policy_gain_delta_pct": 0.0, "policy_signature_delta_pct": 0.0}), encoding="utf-8")
            (root / "clean.json").write_text(json.dumps({"comparison_valid": False, "baseline_policy_valid": False, "alternative_policy_valid": False}), encoding="utf-8")
            (root / "adj.json").write_text(json.dumps({"dispatch_policy_support_status": "invalid"}), encoding="utf-8")
            (root / "handoff.json").write_text(json.dumps({"v0_4_x_next_step": "run_one_more_policy_comparison"}), encoding="utf-8")
            payload = build_v045_closeout(
                v0_4_3_closeout_path=str(root / "v043" / "closeout.json"),
                v0_4_4_closeout_path=str(root / "v044" / "closeout.json"),
                policy_slice_lock_path=str(root / "lock.json"),
                policy_comparison_path=str(root / "comparison.json"),
                policy_cleanliness_path=str(root / "clean.json"),
                policy_adjudication_path=str(root / "adj.json"),
                v0_4_6_handoff_path=str(root / "handoff.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_4_5_policy_comparison_invalid")


if __name__ == "__main__":
    unittest.main()
