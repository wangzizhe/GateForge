from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_5_1_boundary_taxonomy import build_v051_boundary_taxonomy
from gateforge.agent_modelica_v0_5_1_case_classification import build_v051_case_classification
from gateforge.agent_modelica_v0_5_1_closeout import build_v051_closeout
from gateforge.agent_modelica_v0_5_1_frozen_slice_integrity import build_v051_frozen_slice_integrity


class AgentModelicaV051BoundaryMapFlowTests(unittest.TestCase):
    def _write_v050_closeout(self, path: Path, *, promoted: bool = True) -> None:
        task_rows = [
            {"task_id": "gen_simple_rc_lowpass_filter", "family_id": "component_api_alignment", "slice_class": "already-covered", "qualitative_bucket": "none"},
            {"task_id": "gen_medium_dc_motor_pi_speed", "family_id": "component_api_alignment", "slice_class": "already-covered", "qualitative_bucket": "none"},
            {"task_id": "gen_medium_two_room_thermal_control", "family_id": "local_interface_alignment", "slice_class": "already-covered", "qualitative_bucket": "none"},
            {"task_id": "gen_complex_ev_thermal_management", "family_id": "local_interface_alignment", "slice_class": "boundary-adjacent", "qualitative_bucket": "cross_domain_interface_pressure"},
            {"task_id": "gen_complex_multi_tank_heat_exchange", "family_id": "medium_redeclare_alignment", "slice_class": "boundary-adjacent", "qualitative_bucket": "medium_cluster_boundary_pressure"},
            {"task_id": "gen_complex_chilled_water_distribution", "family_id": "medium_redeclare_alignment", "slice_class": "undeclared-but-bounded-candidate", "qualitative_bucket": "fluid_network_medium_surface_pressure"},
            {"task_id": "gen_complex_heat_pump_buffer_tank_loop", "family_id": "medium_redeclare_alignment", "slice_class": "undeclared-but-bounded-candidate", "qualitative_bucket": "fluid_network_medium_surface_pressure"},
        ]
        payload = {
            "conclusion": {
                "version_decision": "v0_5_0_widened_real_substrate_ready",
                "widened_real_substrate_status": "ready",
                "qualitative_widening_confirmed": True,
            },
            "candidate_pack": {
                "candidate_slice_classification_rules_frozen": True,
                "task_rows": task_rows,
            },
            "dispatch_cleanliness_audit": {
                "dispatch_cleanliness_admission": "promoted" if promoted else "degraded_but_executable",
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v051_reports_ready_when_boundary_buckets_are_interpretable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v050 = root / "v050" / "summary.json"
            self._write_v050_closeout(v050, promoted=True)

            build_v051_frozen_slice_integrity(v0_5_0_closeout_path=str(v050), out_dir=str(root / "integrity"))
            build_v051_boundary_taxonomy(out_dir=str(root / "taxonomy"))
            build_v051_case_classification(
                v0_5_0_closeout_path=str(v050),
                frozen_slice_integrity_path=str(root / "integrity" / "summary.json"),
                boundary_taxonomy_path=str(root / "taxonomy" / "summary.json"),
                out_dir=str(root / "classification"),
            )
            payload = build_v051_closeout(
                v0_5_0_closeout_path=str(v050),
                frozen_slice_integrity_path=str(root / "integrity" / "summary.json"),
                boundary_taxonomy_path=str(root / "taxonomy" / "summary.json"),
                case_classification_path=str(root / "classification" / "summary.json"),
                boundary_readiness_path=str(root / "readiness" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_1_boundary_map_ready")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_5_2_handoff_mode"), "run_targeted_expansion_on_bounded_uncovered_slice")

    def test_v051_reports_not_ready_when_dispatch_cleanliness_is_not_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v050 = root / "v050" / "summary.json"
            self._write_v050_closeout(v050, promoted=False)

            payload = build_v051_closeout(
                v0_5_0_closeout_path=str(v050),
                frozen_slice_integrity_path=str(root / "integrity" / "summary.json"),
                boundary_taxonomy_path=str(root / "taxonomy" / "summary.json"),
                case_classification_path=str(root / "classification" / "summary.json"),
                boundary_readiness_path=str(root / "readiness" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_1_boundary_map_not_ready")


if __name__ == "__main__":
    unittest.main()
