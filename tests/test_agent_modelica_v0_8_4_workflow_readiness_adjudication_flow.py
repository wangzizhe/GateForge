from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_8_4_closeout import build_v084_closeout
from gateforge.agent_modelica_v0_8_4_frozen_baseline_adjudication import (
    build_v084_frozen_baseline_adjudication,
)
from gateforge.agent_modelica_v0_8_4_handoff_integrity import build_v084_handoff_integrity
from gateforge.agent_modelica_v0_8_4_route_interpretation_summary import (
    build_v084_route_interpretation_summary,
)


class AgentModelicaV084WorkflowReadinessAdjudicationFlowTests(unittest.TestCase):
    def _write_upstream_chain(self, root: Path) -> tuple[Path, Path, Path, Path]:
        v083 = {
            "conclusion": {
                "version_decision": "v0_8_3_threshold_pack_validated",
                "current_baseline_route_observed": "workflow_readiness_partial_but_interpretable",
                "v0_8_4_handoff_mode": "run_late_workflow_readiness_adjudication",
            },
            "handoff_integrity": {
                "upstream_execution_source": "gateforge_run_contract_live_path",
            },
            "threshold_validation_summary": {
                "same_logic_validation_status": "validated",
                "pack_overlap_detected": False,
                "pack_under_specified_detected": False,
            },
        }
        v082_input = {
            "frozen_baseline_metrics": {
                "task_count": 10,
                "workflow_resolution_rate_pct": 40.0,
                "goal_alignment_rate_pct": 60.0,
                "surface_fix_only_rate_pct": 20.0,
                "unresolved_rate_pct": 40.0,
                "workflow_spillover_share_pct": 20.0,
                "dispatch_or_policy_limited_share_pct": 20.0,
                "goal_artifact_missing_after_surface_fix_share_pct": 20.0,
                "profile_barrier_unclassified_count": 0,
                "barrier_label_coverage_rate_pct": 100.0,
                "surface_fix_only_explained_rate_pct": 100.0,
                "unresolved_explained_rate_pct": 100.0,
                "legacy_bucket_mapping_rate_pct": 100.0,
                "profile_run_count": 3,
                "workflow_resolution_rate_range_pct": 0.0,
                "goal_alignment_rate_range_pct": 0.0,
                "per_case_outcome_consistency_rate_pct": 100.0,
            },
            "frozen_barrier_distribution": {
                "goal_artifact_missing_after_surface_fix": 2,
                "dispatch_or_policy_limited_unresolved": 2,
                "workflow_spillover_unresolved": 2,
            },
        }
        v082_freeze = {
            "threshold_pack_status": "FROZEN",
            "supported_threshold_pack": {
                "primary_workflow_metrics": {
                    "workflow_resolution_rate_pct_min": 50.0,
                    "goal_alignment_rate_pct_min": 70.0,
                    "surface_fix_only_rate_pct_max": 20.0,
                    "unresolved_rate_pct_max": 30.0,
                },
                "barrier_sidecar_metrics": {
                    "workflow_spillover_share_pct_max": 20.0,
                    "dispatch_or_policy_limited_share_pct_max": 20.0,
                    "goal_artifact_missing_after_surface_fix_share_pct_max": 20.0,
                    "profile_barrier_unclassified_count_max": 0,
                },
                "interpretability_safeguards": {
                    "barrier_label_coverage_rate_pct_min": 100.0,
                    "surface_fix_only_explained_rate_pct_min": 100.0,
                    "unresolved_explained_rate_pct_min": 100.0,
                    "legacy_bucket_mapping_rate_pct_min": 80.0,
                },
                "repeatability_preconditions": {
                    "profile_run_count_min": 3,
                    "workflow_resolution_rate_range_pct_max": 10.0,
                    "goal_alignment_rate_range_pct_max": 15.0,
                    "per_case_outcome_consistency_rate_pct_min": 80.0,
                },
            },
            "partial_threshold_pack": {
                "primary_workflow_metrics": {
                    "workflow_resolution_rate_pct_min": 40.0,
                    "goal_alignment_rate_pct_min": 60.0,
                    "surface_fix_only_rate_pct_max": 30.0,
                    "unresolved_rate_pct_max": 50.0,
                },
                "barrier_sidecar_metrics": {
                    "workflow_spillover_share_pct_max": 30.0,
                    "dispatch_or_policy_limited_share_pct_max": 30.0,
                    "goal_artifact_missing_after_surface_fix_share_pct_max": 30.0,
                    "profile_barrier_unclassified_count_max": 1,
                },
                "interpretability_safeguards": {
                    "barrier_label_coverage_rate_pct_min": 100.0,
                    "surface_fix_only_explained_rate_pct_min": 100.0,
                    "unresolved_explained_rate_pct_min": 100.0,
                    "legacy_bucket_mapping_rate_pct_min": 70.0,
                },
                "repeatability_preconditions": {
                    "profile_run_count_min": 2,
                    "workflow_resolution_rate_range_pct_max": 20.0,
                    "goal_alignment_rate_range_pct_max": 25.0,
                    "per_case_outcome_consistency_rate_pct_min": 70.0,
                },
            },
        }
        v081_characterization = {
            "profile_barrier_unclassified_count": 0,
            "barrier_label_distribution": {
                "goal_artifact_missing_after_surface_fix": 2,
                "dispatch_or_policy_limited_unresolved": 2,
                "workflow_spillover_unresolved": 2,
            },
        }
        v083_path = root / "v083.json"
        v082_input_path = root / "v082_input.json"
        v082_freeze_path = root / "v082_freeze.json"
        v081_characterization_path = root / "v081_characterization.json"
        v083_path.write_text(json.dumps(v083), encoding="utf-8")
        v082_input_path.write_text(json.dumps(v082_input), encoding="utf-8")
        v082_freeze_path.write_text(json.dumps(v082_freeze), encoding="utf-8")
        v081_characterization_path.write_text(json.dumps(v081_characterization), encoding="utf-8")
        return v083_path, v082_input_path, v082_freeze_path, v081_characterization_path

    def test_handoff_integrity_passes_on_validated_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v083_path, _, _, _ = self._write_upstream_chain(root)
            payload = build_v084_handoff_integrity(
                v083_closeout_path=str(v083_path),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["upstream_baseline_route"], "workflow_readiness_partial_but_interpretable")

    def test_frozen_baseline_adjudication_observes_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, v082_input_path, v082_freeze_path, _ = self._write_upstream_chain(root)
            payload = build_v084_frozen_baseline_adjudication(
                v082_threshold_input_table_path=str(v082_input_path),
                v082_threshold_freeze_path=str(v082_freeze_path),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(payload["adjudication_route"], "workflow_readiness_partial_but_interpretable")
            self.assertEqual(payload["adjudication_route_count"], 1)

    def test_route_summary_stays_interpretable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v083_path, v082_input_path, v082_freeze_path, v081_characterization_path = self._write_upstream_chain(root)
            build_v084_frozen_baseline_adjudication(
                v082_threshold_input_table_path=str(v082_input_path),
                v082_threshold_freeze_path=str(v082_freeze_path),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v084_route_interpretation_summary(
                frozen_baseline_adjudication_path=str(root / "adjudication" / "summary.json"),
                v081_characterization_path=str(v081_characterization_path),
                v082_threshold_input_table_path=str(v082_input_path),
                v083_closeout_path=str(v083_path),
                out_dir=str(root / "summary"),
            )
            self.assertTrue(payload["legacy_bucket_sidecar_still_interpretable"])
            self.assertEqual(payload["adjudication_route"], "workflow_readiness_partial_but_interpretable")

    def test_closeout_reaches_partial_but_interpretable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v083_path, v082_input_path, v082_freeze_path, v081_characterization_path = self._write_upstream_chain(root)
            payload = build_v084_closeout(
                v083_closeout_path=str(v083_path),
                v082_threshold_input_table_path=str(v082_input_path),
                v082_threshold_freeze_path=str(v082_freeze_path),
                v081_characterization_path=str(v081_characterization_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                frozen_baseline_adjudication_path=str(root / "adjudication" / "summary.json"),
                route_interpretation_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_4_workflow_readiness_partial_but_interpretable",
            )
            self.assertEqual(
                payload["conclusion"]["v0_8_5_handoff_mode"],
                "decide_if_one_more_same_logic_refinement_is_worth_it",
            )

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_v083 = {
                "conclusion": {
                    "version_decision": "v0_8_3_threshold_pack_partial",
                    "current_baseline_route_observed": "workflow_readiness_partial_but_interpretable",
                    "v0_8_4_handoff_mode": "repair_threshold_validation_instability_first",
                },
                "handoff_integrity": {
                    "upstream_execution_source": "gateforge_run_contract_live_path",
                },
                "threshold_validation_summary": {
                    "same_logic_validation_status": "partial",
                    "pack_overlap_detected": False,
                    "pack_under_specified_detected": False,
                },
            }
            bad_v083_path = root / "bad_v083.json"
            bad_v083_path.write_text(json.dumps(bad_v083), encoding="utf-8")
            _, v082_input_path, v082_freeze_path, v081_characterization_path = self._write_upstream_chain(root)
            payload = build_v084_closeout(
                v083_closeout_path=str(bad_v083_path),
                v082_threshold_input_table_path=str(v082_input_path),
                v082_threshold_freeze_path=str(v082_freeze_path),
                v081_characterization_path=str(v081_characterization_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                frozen_baseline_adjudication_path=str(root / "adjudication" / "summary.json"),
                route_interpretation_summary_path=str(root / "summary" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_4_handoff_adjudication_inputs_invalid",
            )


if __name__ == "__main__":
    unittest.main()
