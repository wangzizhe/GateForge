from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_31_closeout import build_v0331_closeout
from gateforge.agent_modelica_v0_3_31_coverage_manifest import build_v0331_coverage_manifest
from gateforge.agent_modelica_v0_3_31_first_fix_evidence import build_v0331_first_fix_evidence
from gateforge.agent_modelica_v0_3_31_surface_export_audit import build_v0331_surface_export_audit


class AgentModelicaV0331MediumRedeclareCoverageFlowTests(unittest.TestCase):
    def _write_v0330_ready_closeout(self, root: Path) -> None:
        (root / "v0330").mkdir(parents=True, exist_ok=True)
        (root / "v0330" / "summary.json").write_text(
            json.dumps({"conclusion": {"version_decision": "stage2_medium_redeclare_discovery_ready"}}),
            encoding="utf-8",
        )

    def test_coverage_manifest_passes_in_fixture_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0330_ready_closeout(root)
            payload = build_v0331_coverage_manifest(
                v0330_closeout_path=str(root / "v0330" / "summary.json"),
                out_dir=str(root / "manifest"),
                use_fixture_only=True,
            )
            summary = payload.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("active_single_task_count") or 0), 18)
            self.assertGreaterEqual(int(summary.get("active_dual_task_count") or 0), 10)

    def test_surface_and_first_fix_pass_in_fixture_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0330_ready_closeout(root)
            build_v0331_coverage_manifest(
                v0330_closeout_path=str(root / "v0330" / "summary.json"),
                out_dir=str(root / "manifest"),
                use_fixture_only=True,
            )
            surface = build_v0331_surface_export_audit(
                manifest_path=str(root / "manifest" / "taskset.json"),
                out_dir=str(root / "surface"),
                use_fixture_only=True,
            )
            first_fix = build_v0331_first_fix_evidence(
                surface_audit_path=str(root / "surface" / "summary.json"),
                active_taskset_path=str(root / "surface" / "active_taskset.json"),
                surface_index_path=str(root / "surface" / "surface_index.json"),
                out_dir=str(root / "first_fix"),
                use_fixture_only=True,
            )
            self.assertEqual((surface.get("summary") or {}).get("status"), "PASS")
            self.assertEqual(first_fix.get("status"), "PASS")
            self.assertEqual(first_fix.get("execution_status"), "executed")
            self.assertGreaterEqual(float(first_fix.get("candidate_contains_canonical_rate_pct") or 0.0), 80.0)

    def test_closeout_upgrades_authority_confidence_when_dual_denominator_and_rate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0330_ready_closeout(root)
            (root / "manifest").mkdir(parents=True, exist_ok=True)
            (root / "surface").mkdir(parents=True, exist_ok=True)
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "manifest" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "handoff_substrate_valid": True,
                        "coverage_construction_mode": "promoted",
                        "source_count": 5,
                        "active_single_task_count": 24,
                        "active_dual_task_count": 11,
                        "single_subtype_counts": {
                            "boundary_like": 8,
                            "vessel_or_volume_like": 7,
                            "pipe_or_local_fluid_interface_like": 9,
                        },
                        "dual_subtype_counts": {
                            "boundary_like": 4,
                            "vessel_or_volume_like": 3,
                            "pipe_or_local_fluid_interface_like": 4,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "surface" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "execution_mode": "promoted",
                        "surface_export_success_rate_pct": 100.0,
                        "canonical_in_candidate_rate_pct": 100.0,
                        "export_excluded_count": 0,
                        "canonical_miss_excluded_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            (root / "first_fix" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "execution_status": "executed",
                        "candidate_contains_canonical_rate_pct": 100.0,
                        "candidate_top1_canonical_rate_pct": 100.0,
                        "patch_applied_rate_pct": 100.0,
                        "signature_advance_rate_pct": 100.0,
                        "drift_to_compile_failure_unknown_rate_pct": 0.0,
                        "subtype_breakdown": {
                            "boundary_like": {"task_count": 8, "signature_advance_rate_pct": 100.0},
                            "vessel_or_volume_like": {"task_count": 7, "signature_advance_rate_pct": 100.0},
                            "pipe_or_local_fluid_interface_like": {"task_count": 9, "signature_advance_rate_pct": 100.0},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "dual" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "execution_status": "executed",
                        "post_first_fix_target_bucket_hit_rate_pct": 100.0,
                        "second_residual_medium_redeclare_retained_rate_pct": 100.0,
                        "dual_full_resolution_rate_pct": 100.0,
                        "subtype_breakdown": {
                            "boundary_like": {
                                "task_count": 4,
                                "post_first_fix_target_bucket_hit_rate_pct": 100.0,
                                "second_residual_medium_redeclare_retained_rate_pct": 100.0,
                                "dual_full_resolution_rate_pct": 100.0,
                            },
                            "vessel_or_volume_like": {
                                "task_count": 3,
                                "post_first_fix_target_bucket_hit_rate_pct": 100.0,
                                "second_residual_medium_redeclare_retained_rate_pct": 100.0,
                                "dual_full_resolution_rate_pct": 100.0,
                            },
                            "pipe_or_local_fluid_interface_like": {
                                "task_count": 4,
                                "post_first_fix_target_bucket_hit_rate_pct": 100.0,
                                "second_residual_medium_redeclare_retained_rate_pct": 100.0,
                                "dual_full_resolution_rate_pct": 100.0,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0331_closeout(
                v0330_closeout_path=str(root / "v0330" / "summary.json"),
                manifest_path=str(root / "manifest" / "summary.json"),
                surface_audit_path=str(root / "surface" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            conclusion = payload.get("conclusion") or {}
            self.assertEqual(conclusion.get("version_decision"), "stage2_medium_redeclare_discovery_coverage_ready")
            self.assertEqual(conclusion.get("authority_confidence"), "supported")

    def test_closeout_returns_handoff_invalid_when_v0330_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "v0330").mkdir(parents=True, exist_ok=True)
            (root / "manifest").mkdir(parents=True, exist_ok=True)
            (root / "surface").mkdir(parents=True, exist_ok=True)
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "v0330" / "summary.json").write_text(
                json.dumps({"conclusion": {"version_decision": "stage2_medium_redeclare_first_fix_ready"}}),
                encoding="utf-8",
            )
            (root / "manifest" / "summary.json").write_text(json.dumps({"handoff_substrate_valid": False, "coverage_construction_mode": "handoff_substrate_invalid"}), encoding="utf-8")
            (root / "surface" / "summary.json").write_text(json.dumps({"status": "FAIL", "execution_mode": "handoff_substrate_invalid"}), encoding="utf-8")
            (root / "first_fix" / "summary.json").write_text(json.dumps({"status": "SKIPPED", "execution_status": "not_executed_due_to_surface_export_gate"}), encoding="utf-8")
            (root / "dual" / "summary.json").write_text(json.dumps({"status": "SKIPPED", "execution_status": "not_executed_due_to_first_fix_gate"}), encoding="utf-8")
            payload = build_v0331_closeout(
                v0330_closeout_path=str(root / "v0330" / "summary.json"),
                manifest_path=str(root / "manifest" / "summary.json"),
                surface_audit_path=str(root / "surface" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
