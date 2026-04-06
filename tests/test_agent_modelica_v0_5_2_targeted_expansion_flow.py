from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_5_2_closeout import build_v052_closeout


class AgentModelicaV052TargetedExpansionFlowTests(unittest.TestCase):
    def _write_v051_closeout(self, path: Path, *, promoted: bool = True, bounded_case_count: int = 6) -> None:
        case_rows = []
        for idx in range(6):
            case_rows.append(
                {
                    "task_id": f"covered_case_{idx}",
                    "family_id": "component_api_alignment",
                    "assigned_boundary_bucket": "covered_success",
                    "qualitative_bucket": "none",
                }
            )
        for idx in range(6):
            case_rows.append(
                {
                    "task_id": f"fragile_case_{idx}",
                    "family_id": "local_interface_alignment",
                    "assigned_boundary_bucket": "covered_but_fragile",
                    "qualitative_bucket": "cross_domain_interface_pressure",
                }
            )
        bounded_ids = [
            "gen_complex_liquid_cooling_loop",
            "gen_complex_hydronic_heating_loop",
            "gen_complex_chilled_water_distribution",
            "gen_complex_heat_pump_buffer_tank_loop",
            "gen_complex_solar_thermal_storage_loop",
            "gen_complex_multi_tank_heat_exchange",
        ]
        for idx in range(bounded_case_count):
            task_id = bounded_ids[idx]
            bucket = "fluid_network_medium_surface_pressure" if idx >= 1 else "medium_cluster_boundary_pressure"
            case_rows.append(
                {
                    "task_id": task_id,
                    "family_id": "medium_redeclare_alignment",
                    "assigned_boundary_bucket": "bounded_uncovered_subtype_candidate",
                    "qualitative_bucket": bucket,
                }
            )
        payload = {
            "status": "PASS",
            "frozen_slice_integrity": {
                "dispatch_cleanliness_level": "promoted" if promoted else "degraded_but_executable",
            },
            "case_classification": {
                "case_rows": case_rows,
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v052_reports_entry_ready_for_recurring_bounded_medium_signal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v051 = root / "v051" / "summary.json"
            self._write_v051_closeout(v051, promoted=True, bounded_case_count=6)
            payload = build_v052_closeout(
                v0_5_1_closeout_path=str(v051),
                signal_audit_path=str(root / "signal" / "summary.json"),
                entry_triage_path=str(root / "triage" / "summary.json"),
                entry_spec_path=str(root / "spec" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            conclusion = payload.get("conclusion") or {}
            self.assertEqual(conclusion.get("version_decision"), "v0_5_2_targeted_expansion_entry_ready")
            self.assertEqual(conclusion.get("v0_5_3_handoff_mode"), "run_entry_first_fix_on_targeted_expansion")
            self.assertEqual(conclusion.get("selected_entry_pattern_id"), "medium_redeclare_alignment.fluid_network_medium_surface_pressure")

    def test_v052_returns_not_supported_when_recurring_signal_floor_is_not_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v051 = root / "v051" / "summary.json"
            self._write_v051_closeout(v051, promoted=True, bounded_case_count=3)
            payload = build_v052_closeout(
                v0_5_1_closeout_path=str(v051),
                signal_audit_path=str(root / "signal" / "summary.json"),
                entry_triage_path=str(root / "triage" / "summary.json"),
                entry_spec_path=str(root / "spec" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            conclusion = payload.get("conclusion") or {}
            self.assertEqual(conclusion.get("version_decision"), "v0_5_2_targeted_expansion_not_supported")
            self.assertEqual(conclusion.get("v0_5_3_handoff_mode"), "return_to_broader_real_validation")


if __name__ == "__main__":
    unittest.main()
