from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_28_closeout import build_v0328_closeout
from gateforge.agent_modelica_v0_3_28_coverage_manifest import build_v0328_coverage_manifest
from gateforge.agent_modelica_v0_3_28_patch_contract import build_v0328_patch_contract
from gateforge.agent_modelica_v0_3_28_surface_export_audit import build_v0328_surface_export_audit
from gateforge.agent_modelica_v0_3_28_taskset import build_v0328_taskset


class AgentModelicaV0328CoverageFlowTests(unittest.TestCase):
    def test_manifest_and_fixture_surface_audit_freeze_widened_neighbor_lane(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = build_v0328_coverage_manifest(out_dir=str(root / "manifest"))
            audit = build_v0328_surface_export_audit(
                out_dir=str(root / "audit"),
                surface_index_out_dir=str(root / "surface"),
                taskset_out_dir=str(root / "taskset"),
                use_fixture_only=True,
            )
            summary = manifest.get("summary") or {}
            audit_summary = audit.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("single_task_count") or 0), 28)
            self.assertGreaterEqual(int(summary.get("dual_sidecar_task_count") or 0), 16)
            self.assertEqual(audit_summary.get("status"), "PASS")
            self.assertGreaterEqual(float(audit_summary.get("surface_export_success_rate_pct") or 0.0), 80.0)

    def test_taskset_neighbor_counts_hold_with_precheck(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v0328_surface_export_audit(
                out_dir=str(root / "audit"),
                surface_index_out_dir=str(root / "surface"),
                taskset_out_dir=str(root / "taskset"),
                use_fixture_only=True,
            )
            taskset = build_v0328_taskset(
                surface_index_path=str(root / "surface" / "surface_index.json"),
                out_dir=str(root / "taskset_rebuilt"),
                use_fixture_only=True,
            )
            summary = taskset.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("active_single_task_count") or 0), 28)
            self.assertGreaterEqual(int(summary.get("active_dual_task_count") or 0), 16)
            self.assertEqual(summary.get("coverage_construction_mode"), "promoted")
            self.assertGreaterEqual(float(summary.get("neighbor_post_first_fix_target_bucket_hit_rate_pct") or 0.0), 80.0)

    def test_closeout_partial_when_dual_is_bottleneck_but_first_fix_holds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v0328_coverage_manifest(out_dir=str(root / "manifest"))
            (root / "surface_audit").mkdir(parents=True, exist_ok=True)
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "contract").mkdir(parents=True, exist_ok=True)
            (root / "surface_audit" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "execution_mode": "promoted",
                        "source_mode": "component_type_local_surface",
                        "surface_export_success_rate_pct": 100.0,
                        "fixture_fallback_rate_pct": 0.0,
                        "neighbor_post_first_fix_target_bucket_hit_rate_pct": 100.0,
                        "active_single_task_count": 30,
                        "active_dual_sidecar_task_count": 16,
                        "export_excluded_count": 0,
                        "export_excluded_task_ids": [],
                        "export_excluded_family_mix": {},
                    }
                ),
                encoding="utf-8",
            )
            (root / "first_fix" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "target_first_failure_hit_rate_pct": 90.0,
                        "candidate_contains_canonical_rate_pct": 90.0,
                        "candidate_top1_canonical_rate_pct": 75.0,
                        "patch_applied_rate_pct": 80.0,
                        "focal_patch_hit_rate_pct": 85.0,
                        "signature_advance_rate_pct": 70.0,
                        "drift_to_compile_failure_unknown_rate_pct": 0.0,
                        "drift_task_count": 0,
                        "drift_reason_counts": {},
                        "signature_advance_not_fired_reason_counts": {"wrong_candidate_selected": 2},
                    }
                ),
                encoding="utf-8",
            )
            (root / "dual" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "neighbor_component_second_residual_rate_pct": 40.0,
                        "neighbor_component_second_residual_local_interface_retained_rate_pct": 40.0,
                        "neighbor_component_dual_full_resolution_rate_pct": 30.0,
                        "signal_port_neighbor_second_residual_rate_pct": 50.0,
                        "signal_port_neighbor_dual_full_resolution_rate_pct": 40.0,
                        "connector_side_neighbor_second_residual_rate_pct": 30.0,
                        "connector_side_neighbor_dual_full_resolution_rate_pct": 20.0,
                        "second_residual_local_interface_retained_count": 6,
                        "full_dual_resolution_count": 5,
                        "task_count": 16,
                    }
                ),
                encoding="utf-8",
            )
            build_v0328_patch_contract(out_dir=str(root / "contract"))
            closeout = build_v0328_closeout(
                manifest_path=str(root / "manifest" / "summary.json"),
                surface_audit_path=str(root / "surface_audit" / "summary.json"),
                patch_contract_path=str(root / "contract" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            conclusion = closeout.get("conclusion") or {}
            self.assertEqual(conclusion.get("version_decision"), "stage2_neighbor_component_local_interface_discovery_coverage_partially_ready")


if __name__ == "__main__":
    unittest.main()
