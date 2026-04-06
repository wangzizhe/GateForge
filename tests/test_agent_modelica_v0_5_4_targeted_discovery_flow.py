from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_5_4_closeout import build_v054_closeout


class AgentModelicaV054TargetedDiscoveryFlowTests(unittest.TestCase):
    def _write_v053_closeout(self, path: Path, *, first_fix_ready: bool = True) -> None:
        payload = {
            "status": "PASS",
            "conclusion": {
                "entry_pattern_id": "medium_redeclare_alignment.fluid_network_medium_surface_pressure",
                "first_fix_ready": first_fix_ready,
            },
            "entry_taskset": {
                "entry_taskset_frozen": True,
                "promoted_case_table": [
                    {"task_id": "gen_complex_hydronic_heating_loop"},
                    {"task_id": "gen_complex_chilled_water_distribution"},
                    {"task_id": "gen_complex_heat_pump_buffer_tank_loop"},
                    {"task_id": "gen_complex_solar_thermal_storage_loop"},
                ],
                "excluded_case_table": [
                    {"task_id": "gen_complex_liquid_cooling_loop", "qualitative_bucket": "medium_cluster_boundary_pressure"},
                ],
            },
            "first_fix_adjudication": {
                "entry_execution_interpretation": {
                    "anti_expansion_boundary_preserved": first_fix_ready,
                },
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v054_reports_discovery_ready_for_clean_second_residual_probe(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v053 = root / "v053" / "summary.json"
            self._write_v053_closeout(v053, first_fix_ready=True)
            payload = build_v054_closeout(
                v0_5_3_closeout_path=str(v053),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                discovery_probe_taskset_path=str(root / "taskset" / "summary.json"),
                residual_exposure_path=str(root / "residual" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_4_targeted_expansion_discovery_ready")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_5_5_handoff_mode"), "run_widened_confirmation_on_targeted_expansion")

    def test_v054_reports_handoff_invalid_when_first_fix_lane_is_not_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v053 = root / "v053" / "summary.json"
            self._write_v053_closeout(v053, first_fix_ready=False)
            payload = build_v054_closeout(
                v0_5_3_closeout_path=str(v053),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                discovery_probe_taskset_path=str(root / "taskset" / "summary.json"),
                residual_exposure_path=str(root / "residual" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_4_handoff_substrate_invalid")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_5_5_handoff_mode"), "return_to_boundary_mapping_for_reassessment")


if __name__ == "__main__":
    unittest.main()
