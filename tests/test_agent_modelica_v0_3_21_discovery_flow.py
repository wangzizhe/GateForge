from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_21_closeout import build_v0321_closeout
from gateforge.agent_modelica_v0_3_21_common import (
    SURFACE_INDEX_FIXTURE,
    apply_discovery_first_fix,
    rank_class_path_candidates,
    rank_parameter_candidates,
)
from gateforge.agent_modelica_v0_3_21_surface_index import build_v0321_surface_index
from gateforge.agent_modelica_v0_3_21_taskset import build_v0321_taskset


class AgentModelicaV0321DiscoveryFlowTests(unittest.TestCase):
    def test_surface_index_fixture_and_taskset_freeze_discovery_lane(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            surface = build_v0321_surface_index(out_dir=str(root / "surface"), use_fixture_only=True)
            taskset = build_v0321_taskset(
                surface_index_path=str(root / "surface" / "surface_index.json"),
                out_dir=str(root / "taskset"),
            )
            summary = surface.get("summary") or {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("source_mode"), "fixture_fallback")
            self.assertEqual((taskset.get("summary") or {}).get("single_task_count"), 6)
            self.assertEqual((taskset.get("summary") or {}).get("dual_sidecar_task_count"), 6)

    def test_discovery_ranking_prefers_expected_candidates(self) -> None:
        ranked_classes = rank_class_path_candidates(
            wrong_symbol="Modelica.Blocks.Source.Sine",
            candidates=list((SURFACE_INDEX_FIXTURE.get("class_path_candidates") or {}).get("Modelica.Blocks.Source.Sine") or []),
        )
        self.assertEqual(ranked_classes[0]["candidate"], "Modelica.Blocks.Sources.Sine")
        ranked_parameters = rank_parameter_candidates(
            wrong_symbol="freqHz",
            candidate_records=list((SURFACE_INDEX_FIXTURE.get("parameter_surface_records") or {}).get(repr(("Modelica.Blocks.Sources.Sine", "freqHz"))) or []),
        )
        self.assertEqual(ranked_parameters[0]["candidate"], "f")

    def test_discovery_patch_uses_top1_candidate_without_direct_mapping(self) -> None:
        patched, audit = apply_discovery_first_fix(
            current_text="Modelica.Blocks.Source.Sine sine(freqHz = 0.5, amplitude = 5.0);",
            patch_type="replace_class_path",
            wrong_symbol="Modelica.Blocks.Source.Sine",
            component_type="Modelica.Blocks.Sources.Sine",
            canonical_symbol="Modelica.Blocks.Sources.Sine",
            class_candidates=list((SURFACE_INDEX_FIXTURE.get("class_path_candidates") or {}).get("Modelica.Blocks.Source.Sine") or []),
        )
        self.assertTrue(audit.get("applied"))
        self.assertTrue(audit.get("candidate_top1_is_canonical"))
        self.assertIn("Modelica.Blocks.Sources.Sine", patched)

    def test_closeout_promotes_ready_with_fixture_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_v0321_surface_index(out_dir=str(root / "surface"), use_fixture_only=True)
            build_v0321_taskset(
                surface_index_path=str(root / "surface" / "surface_index.json"),
                out_dir=str(root / "taskset"),
            )
            (root / "first_fix").mkdir(parents=True, exist_ok=True)
            (root / "dual").mkdir(parents=True, exist_ok=True)
            (root / "first_fix" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "candidate_contains_canonical_rate_pct": 100.0,
                        "candidate_top1_canonical_rate_pct": 83.3,
                        "parameter_discovery_top1_canonical_rate_pct": 66.7,
                        "class_path_discovery_top1_canonical_rate_pct": 100.0,
                        "patch_applied_rate_pct": 100.0,
                        "signature_advance_rate_pct": 83.3,
                        "admitted_task_count": 5,
                        "advance_mode_counts": {"resolved_after_first_fix": 4, "secondary_error_exposed_early": 1},
                        "signature_advance_not_fired_reason_counts": {"wrong_candidate_selected": 1},
                    }
                ),
                encoding="utf-8",
            )
            (root / "dual" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "first_fix_discovery_ready": True,
                        "second_residual_exposed_count": 4,
                        "second_residual_undefined_symbol_count": 4,
                        "full_dual_resolution_count": 4,
                    }
                ),
                encoding="utf-8",
            )
            closeout = build_v0321_closeout(
                surface_index_path=str(root / "surface" / "summary.json"),
                taskset_path=str(root / "taskset" / "summary.json"),
                first_fix_path=str(root / "first_fix" / "summary.json"),
                dual_recheck_path=str(root / "dual" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((closeout.get("conclusion") or {}).get("version_decision"), "stage2_api_discovery_ready")


if __name__ == "__main__":
    unittest.main()
