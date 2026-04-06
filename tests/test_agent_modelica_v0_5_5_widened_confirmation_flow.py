from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_5_5_closeout import build_v055_closeout


class AgentModelicaV055WidenedConfirmationFlowTests(unittest.TestCase):
    def _write_v054_closeout(self, path: Path, *, discovery_ready: bool = True) -> None:
        payload = {
            "status": "PASS",
            "conclusion": {
                "entry_pattern_id": "medium_redeclare_alignment.fluid_network_medium_surface_pressure",
                "discovery_ready": discovery_ready,
            },
            "handoff_integrity": {
                "anti_expansion_boundary_intact": discovery_ready,
            },
            "discovery_adjudication": {
                "residual_interpretation": {
                    "residual_stays_bounded": discovery_ready,
                },
            },
            "discovery_probe_taskset": {
                "probe_case_table": [
                    {"task_id": "gen_complex_hydronic_heating_loop"},
                    {"task_id": "gen_complex_chilled_water_distribution"},
                    {"task_id": "gen_complex_heat_pump_buffer_tank_loop"},
                    {"task_id": "gen_complex_solar_thermal_storage_loop"},
                ],
                "excluded_probe_case_table": [
                    {"task_id": "gen_complex_liquid_cooling_loop", "qualitative_bucket": "medium_cluster_boundary_pressure"},
                    {"task_id": "gen_complex_multi_tank_heat_exchange", "qualitative_bucket": "medium_cluster_boundary_pressure"},
                ],
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v055_reports_widened_ready_for_clean_expanded_slice(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v054 = root / "v054" / "summary.json"
            self._write_v054_closeout(v054, discovery_ready=True)
            payload = build_v055_closeout(
                v0_5_4_closeout_path=str(v054),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                widened_manifest_path=str(root / "manifest" / "summary.json"),
                widened_execution_path=str(root / "execution" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_5_targeted_expansion_widened_ready")
            self.assertEqual((payload.get("conclusion") or {}).get("branch_status"), "widened_and_stable")

    def test_v055_reports_handoff_invalid_when_discovery_lane_is_not_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v054 = root / "v054" / "summary.json"
            self._write_v054_closeout(v054, discovery_ready=False)
            payload = build_v055_closeout(
                v0_5_4_closeout_path=str(v054),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                widened_manifest_path=str(root / "manifest" / "summary.json"),
                widened_execution_path=str(root / "execution" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_5_handoff_substrate_invalid")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_5_6_handoff_mode"), "return_to_boundary_mapping_for_reassessment")


if __name__ == "__main__":
    unittest.main()
