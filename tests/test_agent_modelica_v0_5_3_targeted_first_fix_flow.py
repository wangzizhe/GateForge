from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_5_3_closeout import build_v053_closeout


class AgentModelicaV053TargetedFirstFixFlowTests(unittest.TestCase):
    def _write_v052_closeout(self, path: Path, *, entry_ready: bool = True) -> None:
        payload = {
            "status": "PASS",
            "conclusion": {
                "selected_entry_pattern_id": "medium_redeclare_alignment.fluid_network_medium_surface_pressure",
                "entry_ready": entry_ready,
            },
            "entry_spec": {
                "allowed_patch_types": [
                    "replace_redeclare_medium_package_path",
                    "align_local_medium_redeclare_clause",
                ],
                "target_first_failure_bucket": "stage_2_structural_balance_reference|undefined_symbol",
                "anti_expansion_boundary_rules": [
                    "disallow topology-heavy patch or cross-component network rewrite",
                    "disallow cross-stage scope expansion beyond local medium redeclare alignment",
                ],
            },
            "entry_triage": {
                "selected_entry_task_ids": [
                    "gen_complex_hydronic_heating_loop",
                    "gen_complex_chilled_water_distribution",
                    "gen_complex_heat_pump_buffer_tank_loop",
                    "gen_complex_solar_thermal_storage_loop",
                ],
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v051_closeout(self, path: Path) -> None:
        case_rows = []
        for task_id in [
            "gen_complex_hydronic_heating_loop",
            "gen_complex_chilled_water_distribution",
            "gen_complex_heat_pump_buffer_tank_loop",
            "gen_complex_solar_thermal_storage_loop",
            "gen_complex_multi_tank_heat_exchange",
        ]:
            bucket = "fluid_network_medium_surface_pressure" if "multi_tank" not in task_id else "medium_cluster_boundary_pressure"
            case_rows.append(
                {
                    "task_id": task_id,
                    "family_id": "medium_redeclare_alignment",
                    "qualitative_bucket": bucket,
                    "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
                }
            )
        payload = {"case_classification": {"case_rows": case_rows}}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v053_reports_first_fix_ready_for_frozen_entry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v052 = root / "v052" / "summary.json"
            v051 = root / "v051" / "summary.json"
            self._write_v052_closeout(v052, entry_ready=True)
            self._write_v051_closeout(v051)
            payload = build_v053_closeout(
                v0_5_2_closeout_path=str(v052),
                v0_5_1_closeout_path=str(v051),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                entry_taskset_path=str(root / "taskset" / "summary.json"),
                first_fix_evidence_path=str(root / "evidence" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_3_targeted_expansion_first_fix_ready")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_5_4_handoff_mode"), "run_discovery_probe_on_targeted_expansion")

    def test_v053_reports_handoff_substrate_invalid_when_entry_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v052 = root / "v052" / "summary.json"
            v051 = root / "v051" / "summary.json"
            self._write_v052_closeout(v052, entry_ready=False)
            self._write_v051_closeout(v051)
            payload = build_v053_closeout(
                v0_5_2_closeout_path=str(v052),
                v0_5_1_closeout_path=str(v051),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                entry_taskset_path=str(root / "taskset" / "summary.json"),
                first_fix_evidence_path=str(root / "evidence" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_3_handoff_substrate_invalid")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_5_4_handoff_mode"), "return_to_boundary_mapping_for_reassessment")


if __name__ == "__main__":
    unittest.main()
