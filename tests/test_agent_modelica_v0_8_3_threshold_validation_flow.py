from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_8_3_closeout import build_v083_closeout
from gateforge.agent_modelica_v0_8_3_threshold_validation_replay_pack import (
    build_v083_threshold_validation_replay_pack,
)
from gateforge.agent_modelica_v0_8_3_threshold_validation_summary import (
    build_v083_threshold_validation_summary,
)


class AgentModelicaV083ThresholdValidationFlowTests(unittest.TestCase):
    def _write_v082_frozen(self, root: Path) -> tuple[Path, Path]:
        v082 = {
            "conclusion": {
                "version_decision": "v0_8_2_workflow_readiness_thresholds_frozen",
                "anti_tautology_pass": True,
                "integer_safe_pass": True,
                "class_distinction_pass": True,
                "v0_8_3_handoff_mode": "validate_frozen_workflow_readiness_threshold_pack",
            },
            "handoff_integrity": {
                "execution_source": "gateforge_run_contract_live_path",
            },
            "threshold_input_table": {
                "frozen_barrier_distribution": {
                    "goal_artifact_missing_after_surface_fix": 2,
                    "dispatch_or_policy_limited_unresolved": 2,
                    "workflow_spillover_unresolved": 2,
                }
            },
            "threshold_freeze": {
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
            },
        }
        v081_replay = {
            "profile_run_count": 3,
            "execution_source": "gateforge_run_contract_live_path",
            "mock_executor_path_used": False,
            "workflow_resolution_rate_range_pct": 0.0,
            "goal_alignment_rate_range_pct": 0.0,
            "per_case_outcome_consistency_rate_pct": 100.0,
            "case_consistency_table": [{} for _ in range(10)],
            "runs": [
                {
                    "run_index": 1,
                    "workflow_resolution_rate_pct": 40.0,
                    "goal_alignment_rate_pct": 60.0,
                    "surface_fix_only_rate_pct": 20.0,
                    "unresolved_rate_pct": 40.0,
                },
                {
                    "run_index": 2,
                    "workflow_resolution_rate_pct": 40.0,
                    "goal_alignment_rate_pct": 60.0,
                    "surface_fix_only_rate_pct": 20.0,
                    "unresolved_rate_pct": 40.0,
                },
                {
                    "run_index": 3,
                    "workflow_resolution_rate_pct": 40.0,
                    "goal_alignment_rate_pct": 60.0,
                    "surface_fix_only_rate_pct": 20.0,
                    "unresolved_rate_pct": 40.0,
                },
            ],
        }
        v082_path = root / "v082_closeout.json"
        v081_replay_path = root / "v081_replay.json"
        v082_path.write_text(json.dumps(v082), encoding="utf-8")
        v081_replay_path.write_text(json.dumps(v081_replay), encoding="utf-8")
        return v082_path, v081_replay_path

    def test_validation_replay_pack_observes_partial_route(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v082_path, v081_replay_path = self._write_v082_frozen(root)
            payload = build_v083_threshold_validation_replay_pack(
                v081_replay_pack_path=str(v081_replay_path),
                v082_closeout_path=str(v082_path),
                out_dir=str(root / "replay"),
            )
            self.assertEqual(payload["pack_input_source"], "frozen_v081_replay_artifact")
            self.assertEqual(payload["canonical_adjudication_route"], "workflow_readiness_partial_but_interpretable")
            self.assertEqual(payload["adjudication_route_flip_count"], 0)

    def test_validation_summary_marks_same_logic_validated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v082_path, v081_replay_path = self._write_v082_frozen(root)
            build_v083_threshold_validation_replay_pack(
                v081_replay_pack_path=str(v081_replay_path),
                v082_closeout_path=str(v082_path),
                out_dir=str(root / "replay"),
            )
            payload = build_v083_threshold_validation_summary(
                validation_replay_pack_path=str(root / "replay" / "summary.json"),
                out_dir=str(root / "summary"),
            )
            self.assertEqual(payload["current_baseline_route_observed"], "workflow_readiness_partial_but_interpretable")
            self.assertEqual(payload["same_logic_validation_status"], "validated")
            self.assertEqual(payload["flip_coincides_with_boundary_crossing"], "not_applicable")

    def test_closeout_reaches_threshold_pack_validated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v082_path, v081_replay_path = self._write_v082_frozen(root)
            payload = build_v083_closeout(
                v081_replay_pack_path=str(v081_replay_path),
                v082_closeout_path=str(v082_path),
                out_dir=str(root / "closeout"),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                validation_replay_pack_path=str(root / "replay" / "summary.json"),
                validation_summary_path=str(root / "summary" / "summary.json"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_8_3_threshold_pack_validated")
            self.assertEqual(payload["conclusion"]["v0_8_4_handoff_mode"], "run_late_workflow_readiness_adjudication")

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad = {
                "conclusion": {
                    "version_decision": "v0_8_2_workflow_readiness_thresholds_partial",
                    "v0_8_3_handoff_mode": "repair_threshold_pack_justification_first",
                },
                "threshold_freeze": {"threshold_pack_status": "FROZEN"},
            }
            bad_v082 = root / "bad_v082.json"
            bad_v082.write_text(json.dumps(bad), encoding="utf-8")
            _, v081_replay_path = self._write_v082_frozen(root)
            payload = build_v083_closeout(
                v081_replay_pack_path=str(v081_replay_path),
                v082_closeout_path=str(bad_v082),
                out_dir=str(root / "closeout"),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                validation_replay_pack_path=str(root / "replay" / "summary.json"),
                validation_summary_path=str(root / "summary" / "summary.json"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_8_3_handoff_validation_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
