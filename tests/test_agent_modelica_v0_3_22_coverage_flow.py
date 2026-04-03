from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_22_closeout import build_v0322_closeout
from gateforge.agent_modelica_v0_3_22_coverage_manifest import build_v0322_coverage_manifest
from gateforge.agent_modelica_v0_3_22_surface_export_audit import build_v0322_surface_export_audit
from gateforge.agent_modelica_v0_3_22_taskset import build_v0322_taskset


class AgentModelicaV0322CoverageFlowTests(unittest.TestCase):
    def test_manifest_and_fixture_surface_audit_freeze_expanded_lane(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = build_v0322_coverage_manifest(out_dir=str(root / "manifest"))
            audit = build_v0322_surface_export_audit(
                out_dir=str(root / "audit"),
                surface_index_out_dir=str(root / "surface"),
                taskset_out_dir=str(root / "taskset"),
                use_fixture_only=True,
            )
            summary = manifest.get("summary") or {}
            audit_summary = audit.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("single_task_count") or 0), 12)
            self.assertGreaterEqual(int(summary.get("dual_sidecar_task_count") or 0), 12)
            self.assertEqual(audit_summary.get("status"), "FAIL")
            self.assertEqual(audit_summary.get("execution_mode"), "blocked_surface_export")
            self.assertGreater(int(audit_summary.get("export_excluded_count") or 0), 0)

    def test_taskset_coverage_counts_expand_beyond_v0321(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v0322_surface_export_audit(
                out_dir=str(root / "audit"),
                surface_index_out_dir=str(root / "surface"),
                taskset_out_dir=str(root / "taskset"),
                use_fixture_only=True,
            )
            taskset = build_v0322_taskset(
                surface_index_path=str(root / "surface" / "surface_index.json"),
                out_dir=str(root / "taskset_rebuilt"),
                use_fixture_only=True,
            )
            summary = taskset.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("single_task_count"), 15)
            self.assertEqual(summary.get("dual_sidecar_task_count"), 12)

    def test_closeout_partial_when_export_degrades_but_discovery_metrics_hold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v0322_coverage_manifest(out_dir=str(root / "manifest"))
            (root / "audit").mkdir(parents=True, exist_ok=True)
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "audit" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "execution_mode": "degraded_with_export_exclusions",
                        "surface_export_success_rate_pct": 85.0,
                        "surface_contains_expected_symbol_rate_pct": 85.0,
                        "inherited_parameter_retention_rate_pct": 100.0,
                        "fixture_fallback_rate_pct": 15.0,
                        "export_excluded_count": 3,
                        "export_excluded_family_mix": {"electrical_sine_voltage": 3},
                    }
                ),
                encoding="utf-8",
            )
            (root / "first_fix" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "candidate_contains_canonical_rate_pct": 90.0,
                        "candidate_top1_canonical_rate_pct": 75.0,
                        "parameter_discovery_top1_canonical_rate_pct": 70.0,
                        "class_path_discovery_top1_canonical_rate_pct": 80.0,
                        "patch_applied_rate_pct": 80.0,
                        "signature_advance_rate_pct": 70.0,
                        "secondary_error_exposed_early_rate_pct": 20.0,
                        "signature_advance_not_fired_reason_counts": {"wrong_candidate_selected": 2},
                    }
                ),
                encoding="utf-8",
            )
            (root / "dual" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "same_component_second_residual_rate_pct": 50.0,
                        "same_component_full_resolution_rate_pct": 30.0,
                        "second_residual_exposed_count": 6,
                        "full_dual_resolution_count": 4,
                    }
                ),
                encoding="utf-8",
            )
            closeout = build_v0322_closeout(
                manifest_path=str(root / "manifest" / "summary.json"),
                surface_audit_path=str(root / "audit" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            conclusion = closeout.get("conclusion") or {}
            self.assertEqual(conclusion.get("version_decision"), "stage2_api_discovery_coverage_partial")
            self.assertEqual(conclusion.get("primary_bottleneck_layer"), "dual_multiround")


if __name__ == "__main__":
    unittest.main()
