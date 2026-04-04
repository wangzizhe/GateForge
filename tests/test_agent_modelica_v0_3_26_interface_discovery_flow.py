from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_26_closeout import build_v0326_closeout
from gateforge.agent_modelica_v0_3_26_common import apply_interface_discovery_first_fix, build_surface_index_payload
from gateforge.agent_modelica_v0_3_26_patch_contract import build_v0326_patch_contract
from gateforge.agent_modelica_v0_3_26_taskset import build_v0326_taskset


class AgentModelicaV0326InterfaceDiscoveryFlowTests(unittest.TestCase):
    def test_surface_index_uses_component_type_local_candidates(self) -> None:
        payload = build_surface_index_payload()
        records = payload.get("surface_records") or {}
        self.assertIn("spring.leftFlange", records)
        self.assertIn("spring.flange_a", (records.get("spring.leftFlange") or {}).get("candidate_symbols") or [])
        self.assertEqual((records.get("spring.leftFlange") or {}).get("component_type"), "Modelica.Mechanics.Translational.Components.Spring")
        self.assertIn("controller.inputSignal", records)
        self.assertIn("controller.u", (records.get("controller.inputSignal") or {}).get("candidate_symbols") or [])

    def test_interface_discovery_patch_prefers_expected_component_type_candidate(self) -> None:
        patched, audit = apply_interface_discovery_first_fix(
            current_text="connect(fixed.flange, spring.leftFlange);",
            patch_type="replace_connect_endpoint",
            wrong_symbol="spring.leftFlange",
            canonical_symbol="spring.flange_a",
            component_family="local_connector_side_alignment",
            candidate_symbols=["spring.flange_a", "spring.flange_b"],
        )
        self.assertTrue(audit.get("applied"))
        self.assertEqual(audit.get("selected_candidate"), "spring.flange_a")
        self.assertIn("spring.flange_a", patched)

    def test_taskset_and_contract_pass_with_component_type_counts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = build_v0326_taskset(out_dir=str(root / "taskset"), use_fixture_only=True)
            contract = build_v0326_patch_contract(out_dir=str(root / "contract"))
            summary = taskset.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("active_single_task_count") or 0), 12)
            self.assertGreaterEqual(int(summary.get("active_dual_task_count") or 0), 10)
            self.assertEqual(contract.get("selection_mode"), "authoritative_component_type_local_interface_surface_only")

    def test_closeout_promotes_component_type_ready_with_fixture_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "manifest").mkdir(parents=True, exist_ok=True)
            (root / "surface_audit").mkdir(parents=True, exist_ok=True)
            (root / "contract").mkdir(parents=True, exist_ok=True)
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "manifest" / "summary.json").write_text(
                json.dumps({"status": "PASS", "source_count": 5, "single_task_count": 25, "dual_sidecar_task_count": 12}),
                encoding="utf-8",
            )
            (root / "surface_audit" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "execution_mode": "promoted",
                        "source_mode": "component_type_local_surface",
                        "surface_export_success_rate_pct": 100.0,
                        "fixture_fallback_rate_pct": 0.0,
                        "active_single_task_count": 25,
                        "active_dual_sidecar_task_count": 12,
                        "export_excluded_count": 0,
                        "export_excluded_task_ids": [],
                        "export_excluded_family_mix": {},
                    }
                ),
                encoding="utf-8",
            )
            build_v0326_patch_contract(out_dir=str(root / "contract"))
            (root / "first_fix" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "target_first_failure_hit_rate_pct": 100.0,
                        "candidate_contains_canonical_rate_pct": 100.0,
                        "candidate_top1_canonical_rate_pct": 85.0,
                        "patch_applied_rate_pct": 90.0,
                        "focal_patch_hit_rate_pct": 90.0,
                        "signature_advance_rate_pct": 80.0,
                        "drift_to_compile_failure_unknown_rate_pct": 0.0,
                        "drift_task_count": 0,
                        "drift_reason_counts": {},
                        "signature_advance_not_fired_reason_counts": {},
                    }
                ),
                encoding="utf-8",
            )
            (root / "dual" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "same_cluster_second_residual_rate_pct": 80.0,
                        "same_cluster_second_residual_local_interface_retained_rate_pct": 80.0,
                        "second_residual_local_interface_retained_count": 9,
                        "dual_full_resolution_rate_pct": 75.0,
                        "full_dual_resolution_count": 9,
                    }
                ),
                encoding="utf-8",
            )
            closeout = build_v0326_closeout(
                manifest_path=str(root / "manifest" / "summary.json"),
                surface_audit_path=str(root / "surface_audit" / "summary.json"),
                patch_contract_path=str(root / "contract" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (closeout.get("conclusion") or {}).get("version_decision"),
                "stage2_component_type_local_interface_discovery_ready",
            )


if __name__ == "__main__":
    unittest.main()
