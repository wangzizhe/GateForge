from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_8_2_closeout import build_v082_closeout
from gateforge.agent_modelica_v0_8_2_threshold_freeze import build_v082_threshold_freeze
from gateforge.agent_modelica_v0_8_2_threshold_input_table import build_v082_threshold_input_table


class AgentModelicaV082ThresholdFreezeFlowTests(unittest.TestCase):
    def _write_v081_characterized(self, root: Path) -> Path:
        payload = {
            "conclusion": {
                "version_decision": "v0_8_1_workflow_readiness_profile_characterized",
                "v0_8_2_handoff_mode": "freeze_workflow_readiness_thresholds_on_characterized_profile",
            },
            "profile_replay_pack": {
                "profile_run_count": 3,
                "execution_source": "gateforge_run_contract_live_path",
                "mock_executor_path_used": False,
                "workflow_resolution_rate_range_pct": 0.0,
                "goal_alignment_rate_range_pct": 0.0,
                "per_case_outcome_consistency_rate_pct": 100.0,
                "runs": [
                    {
                        "workflow_resolution_rate_pct": 40.0,
                        "goal_alignment_rate_pct": 60.0,
                        "surface_fix_only_rate_pct": 20.0,
                        "unresolved_rate_pct": 40.0,
                    }
                ],
            },
            "workflow_profile_characterization": {
                "barrier_label_coverage_rate_pct": 100.0,
                "surface_fix_only_explained_rate_pct": 100.0,
                "unresolved_explained_rate_pct": 100.0,
                "profile_barrier_unclassified_count": 0,
                "case_characterization_table": [{} for _ in range(10)],
                "barrier_label_distribution": {
                    "goal_artifact_missing_after_surface_fix": 2,
                    "dispatch_or_policy_limited_unresolved": 2,
                    "workflow_spillover_unresolved": 2,
                },
                "legacy_bucket_crosswalk_by_outcome": {
                    "unresolved": {
                        "dispatch_or_policy_limited": 2,
                        "topology_or_open_world_spillover": 2,
                    }
                },
            },
        }
        path = root / "v081_closeout.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_threshold_input_table_freezes_current_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v081_path = self._write_v081_characterized(root)
            payload = build_v082_threshold_input_table(
                v081_closeout_path=str(v081_path),
                out_dir=str(root / "inputs"),
            )
            self.assertEqual(payload["frozen_baseline_metrics"]["workflow_resolution_rate_pct"], 40.0)
            self.assertEqual(payload["frozen_baseline_metrics"]["workflow_spillover_share_pct"], 20.0)
            self.assertEqual(
                payload["integer_safe_case_count_equivalents"]["workflow_resolution_rate_pct"], "4/10"
            )

    def test_threshold_freeze_enforces_anti_tautology(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v081_path = self._write_v081_characterized(root)
            build_v082_threshold_input_table(
                v081_closeout_path=str(v081_path),
                out_dir=str(root / "inputs"),
            )
            payload = build_v082_threshold_freeze(
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                out_dir=str(root / "freeze"),
            )
            self.assertTrue(payload["anti_tautology_check"]["pass"])
            self.assertFalse(payload["anti_tautology_check"]["current_v081_baseline_supported"])
            self.assertTrue(payload["anti_tautology_check"]["current_v081_baseline_partial"])

    def test_closeout_reaches_thresholds_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v081_path = self._write_v081_characterized(root)
            payload = build_v082_closeout(
                v081_closeout_path=str(v081_path),
                out_dir=str(root / "closeout"),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                threshold_freeze_path=str(root / "freeze" / "summary.json"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_2_workflow_readiness_thresholds_frozen",
            )
            self.assertEqual(
                payload["conclusion"]["v0_8_3_handoff_mode"],
                "validate_frozen_workflow_readiness_threshold_pack",
            )

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_payload = {
                "conclusion": {
                    "version_decision": "v0_8_1_workflow_readiness_profile_partial",
                    "v0_8_2_handoff_mode": "repair_profile_characterization_gaps_first",
                },
                "profile_replay_pack": {
                    "profile_run_count": 2,
                    "execution_source": "gateforge_run_contract_live_path",
                    "mock_executor_path_used": False,
                },
                "workflow_profile_characterization": {
                    "barrier_label_coverage_rate_pct": 100.0,
                    "profile_barrier_unclassified_count": 0,
                },
            }
            v081_path = root / "bad_v081_closeout.json"
            v081_path.write_text(json.dumps(bad_payload), encoding="utf-8")
            payload = build_v082_closeout(
                v081_closeout_path=str(v081_path),
                out_dir=str(root / "closeout"),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                threshold_freeze_path=str(root / "freeze" / "summary.json"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_2_handoff_threshold_inputs_invalid",
            )


if __name__ == "__main__":
    unittest.main()
