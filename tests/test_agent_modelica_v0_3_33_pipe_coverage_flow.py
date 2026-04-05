from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_33_closeout import build_v0333_closeout
from gateforge.agent_modelica_v0_3_33_coverage_manifest import build_v0333_coverage_manifest
from gateforge.agent_modelica_v0_3_33_dual_recheck import build_v0333_dual_recheck
from gateforge.agent_modelica_v0_3_33_first_fix_evidence import build_v0333_first_fix_evidence
from gateforge.agent_modelica_v0_3_33_surface_export_audit import build_v0333_surface_export_audit


class AgentModelicaV0333PipeCoverageFlowTests(unittest.TestCase):
    def _write_v0331_closeout(self, root: Path) -> None:
        (root / "v0331").mkdir(parents=True, exist_ok=True)
        payload = {
            "conclusion": {
                "version_decision": "stage2_medium_redeclare_discovery_coverage_partially_ready",
                "authority_confidence": "supported",
            },
            "first_fix_evidence": {
                "subtype_breakdown": {
                    "boundary_like": {"task_count": 6},
                    "vessel_or_volume_like": {"task_count": 6},
                }
            },
            "dual_recheck": {
                "subtype_breakdown": {
                    "boundary_like": {
                        "task_count": 6,
                        "second_residual_medium_redeclare_retained_rate_pct": 100.0,
                        "dual_full_resolution_rate_pct": 100.0,
                    },
                    "vessel_or_volume_like": {
                        "task_count": 6,
                        "second_residual_medium_redeclare_retained_rate_pct": 100.0,
                        "dual_full_resolution_rate_pct": 100.0,
                    },
                }
            },
        }
        (root / "v0331" / "summary.json").write_text(json.dumps(payload), encoding="utf-8")

    def _write_v0332_closeout(self, root: Path, decision: str = "stage2_medium_redeclare_pipe_slice_discovery_ready") -> None:
        (root / "v0332").mkdir(parents=True, exist_ok=True)
        (root / "v0332" / "summary.json").write_text(json.dumps({"conclusion": {"version_decision": decision}}), encoding="utf-8")

    def test_manifest_builds_promoted_counts_in_fixture_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0331_closeout(root)
            self._write_v0332_closeout(root)
            payload = build_v0333_coverage_manifest(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                v0332_closeout_path=str(root / "v0332" / "summary.json"),
                out_dir=str(root / "manifest"),
                use_fixture_only=True,
            )
            summary = payload.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("active_single_task_count") or 0), 24)
            self.assertGreaterEqual(int(summary.get("active_dual_task_count") or 0), 12)

    def test_surface_first_fix_and_dual_pass_in_fixture_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0331_closeout(root)
            self._write_v0332_closeout(root)
            build_v0333_coverage_manifest(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                v0332_closeout_path=str(root / "v0332" / "summary.json"),
                out_dir=str(root / "manifest"),
                use_fixture_only=True,
            )
            surface = build_v0333_surface_export_audit(
                manifest_path=str(root / "manifest" / "taskset.json"),
                out_dir=str(root / "surface"),
                use_fixture_only=True,
            )
            first_fix = build_v0333_first_fix_evidence(
                surface_audit_path=str(root / "surface" / "summary.json"),
                active_taskset_path=str(root / "surface" / "active_taskset.json"),
                surface_index_path=str(root / "surface" / "surface_index.json"),
                out_dir=str(root / "first_fix"),
                use_fixture_only=True,
            )
            dual = build_v0333_dual_recheck(
                first_fix_path=str(root / "first_fix" / "summary.json"),
                active_taskset_path=str(root / "surface" / "active_taskset.json"),
                surface_index_path=str(root / "surface" / "surface_index.json"),
                out_dir=str(root / "dual"),
                use_fixture_only=True,
            )
            self.assertEqual((surface.get("summary") or {}).get("status"), "PASS")
            self.assertEqual(first_fix.get("status"), "PASS")
            self.assertEqual(dual.get("status"), "PASS")
            self.assertGreaterEqual(float(first_fix.get("candidate_top1_canonical_rate_pct") or 0.0), 70.0)
            self.assertGreaterEqual(float(dual.get("pipe_slice_dual_full_resolution_rate_pct") or 0.0), 40.0)

    def test_closeout_reaches_coverage_ready_in_fixture_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0331_closeout(root)
            self._write_v0332_closeout(root)
            build_v0333_coverage_manifest(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                v0332_closeout_path=str(root / "v0332" / "summary.json"),
                out_dir=str(root / "manifest"),
                use_fixture_only=True,
            )
            build_v0333_surface_export_audit(
                manifest_path=str(root / "manifest" / "taskset.json"),
                out_dir=str(root / "surface"),
                use_fixture_only=True,
            )
            build_v0333_first_fix_evidence(
                surface_audit_path=str(root / "surface" / "summary.json"),
                active_taskset_path=str(root / "surface" / "active_taskset.json"),
                surface_index_path=str(root / "surface" / "surface_index.json"),
                out_dir=str(root / "first_fix"),
                use_fixture_only=True,
            )
            build_v0333_dual_recheck(
                first_fix_path=str(root / "first_fix" / "summary.json"),
                active_taskset_path=str(root / "surface" / "active_taskset.json"),
                surface_index_path=str(root / "surface" / "surface_index.json"),
                out_dir=str(root / "dual"),
                use_fixture_only=True,
            )
            payload = build_v0333_closeout(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                v0332_closeout_path=str(root / "v0332" / "summary.json"),
                manifest_path=str(root / "manifest" / "summary.json"),
                surface_audit_path=str(root / "surface" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "stage2_medium_redeclare_pipe_slice_coverage_ready")
            self.assertEqual((payload.get("conclusion") or {}).get("third_family_recomposition_status"), "full_widened_authority_ready")

    def test_closeout_returns_handoff_invalid_when_v0332_is_not_consumable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v0331_closeout(root)
            self._write_v0332_closeout(root, decision="stage2_medium_redeclare_pipe_slice_boundary_rejected")
            payload = build_v0333_closeout(
                v0331_closeout_path=str(root / "v0331" / "summary.json"),
                v0332_closeout_path=str(root / "v0332" / "summary.json"),
                manifest_path=str(root / "manifest" / "summary.json"),
                surface_audit_path=str(root / "surface" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
