from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_9_4_closeout import build_v094_closeout
from gateforge.agent_modelica_v0_9_4_expanded_threshold_pack import build_v094_expanded_threshold_pack
from gateforge.agent_modelica_v0_9_4_threshold_input_table import build_v094_threshold_input_table


class AgentModelicaV094ExpandedThresholdFreezeFlowTests(unittest.TestCase):
    def _write_v093_characterized(self, root: Path) -> Path:
        payload = {
            "conclusion": {
                "version_decision": "v0_9_3_expanded_workflow_profile_characterized",
                "v0_9_4_handoff_mode": "freeze_expanded_workflow_thresholds",
            },
            "expanded_profile_replay_pack": {
                "profile_run_count": 3,
                "execution_source": "frozen_expanded_substrate_deterministic_replay",
                "workflow_resolution_rate_range_pct": 0.0,
                "goal_alignment_rate_range_pct": 0.0,
                "unexplained_case_flip_count": 0,
                "per_case_outcome_consistency_rate_pct": 100.0,
            },
            "expanded_workflow_profile_characterization": {
                "expanded_substrate_size": 19,
                "workflow_resolution_rate_pct": 21.1,
                "goal_alignment_rate_pct": 47.4,
                "surface_fix_only_rate_pct": 26.3,
                "unresolved_rate_pct": 52.6,
                "barrier_label_distribution": {
                    "goal_artifact_missing_after_surface_fix": 5,
                    "dispatch_or_policy_limited_unresolved": 5,
                    "workflow_spillover_unresolved": 5,
                },
                "barrier_label_coverage_rate_pct": 100.0,
                "surface_fix_only_explained_rate_pct": 100.0,
                "unresolved_explained_rate_pct": 100.0,
                "profile_barrier_unclassified_count": 0,
                "case_characterization_table": [{} for _ in range(19)],
            },
        }
        path = root / "v093_closeout.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_threshold_input_table_freezes_current_expanded_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v093_path = self._write_v093_characterized(root)
            payload = build_v094_threshold_input_table(
                v093_closeout_path=str(v093_path),
                out_dir=str(root / "inputs"),
            )
            self.assertEqual(payload["frozen_baseline_metrics"]["workflow_resolution_case_count"], 4)
            self.assertEqual(payload["frozen_baseline_metrics"]["goal_alignment_case_count"], 9)
            self.assertEqual(
                payload["integer_safe_case_count_equivalents"]["workflow_resolution_case_count"],
                "4/19 (21.1%)",
            )

    def test_expanded_threshold_pack_enforces_anti_tautology_against_real_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v093_path = self._write_v093_characterized(root)
            build_v094_threshold_input_table(
                v093_closeout_path=str(v093_path),
                out_dir=str(root / "inputs"),
            )
            payload = build_v094_expanded_threshold_pack(
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                out_dir=str(root / "pack"),
            )
            self.assertTrue(payload["anti_tautology_check"]["pass"])
            self.assertFalse(payload["anti_tautology_check"]["current_v093_baseline_supported"])
            self.assertTrue(payload["anti_tautology_check"]["current_v093_baseline_partial"])

    def test_closeout_reaches_thresholds_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v093_path = self._write_v093_characterized(root)
            payload = build_v094_closeout(
                v093_closeout_path=str(v093_path),
                out_dir=str(root / "closeout"),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                expanded_threshold_pack_path=str(root / "pack" / "summary.json"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_4_expanded_workflow_thresholds_frozen")
            self.assertEqual(
                payload["conclusion"]["v0_9_5_handoff_mode"],
                "adjudicate_expanded_workflow_readiness_against_frozen_thresholds",
            )

    def test_closeout_routes_to_partial_when_execution_posture_note_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v093_path = self._write_v093_characterized(root)
            build_v094_threshold_input_table(
                v093_closeout_path=str(v093_path),
                out_dir=str(root / "inputs"),
            )
            pack_payload = build_v094_expanded_threshold_pack(
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                out_dir=str(root / "pack"),
            )
            pack_payload["execution_posture_semantics_check"]["pass"] = False
            pack_payload["status"] = "FAIL"
            pack_path = root / "pack" / "summary.json"
            pack_path.write_text(json.dumps(pack_payload), encoding="utf-8")
            payload = build_v094_closeout(
                v093_closeout_path=str(v093_path),
                out_dir=str(root / "closeout"),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                expanded_threshold_pack_path=str(pack_path),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_4_expanded_workflow_thresholds_partial")

    def test_closeout_returns_invalid_when_threshold_ordering_collapses(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v093_path = self._write_v093_characterized(root)
            build_v094_threshold_input_table(
                v093_closeout_path=str(v093_path),
                out_dir=str(root / "inputs"),
            )
            pack_payload = build_v094_expanded_threshold_pack(
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                out_dir=str(root / "pack"),
            )
            pack_payload["threshold_ordering_check"]["pass"] = False
            pack_payload["threshold_ordering_check"]["checks"]["workflow_resolution_case_count_ordered"] = False
            pack_payload["baseline_classification_under_frozen_pack"] = "fallback_to_profile_clarification_or_expansion_needed"
            pack_payload["status"] = "FAIL"
            pack_path = root / "pack" / "summary.json"
            pack_path.write_text(json.dumps(pack_payload), encoding="utf-8")
            payload = build_v094_closeout(
                v093_closeout_path=str(v093_path),
                out_dir=str(root / "closeout"),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                expanded_threshold_pack_path=str(pack_path),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_4_expanded_workflow_thresholds_invalid")

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_payload = {
                "conclusion": {
                    "version_decision": "v0_9_3_expanded_workflow_profile_partial",
                    "v0_9_4_handoff_mode": "clarify_expanded_profile_before_threshold_freeze",
                },
                "expanded_profile_replay_pack": {
                    "profile_run_count": 2,
                    "execution_source": "frozen_expanded_substrate_deterministic_replay",
                    "unexplained_case_flip_count": 2,
                    "per_case_outcome_consistency_rate_pct": 90.0,
                    "workflow_resolution_rate_range_pct": 5.0,
                    "goal_alignment_rate_range_pct": 5.0,
                },
                "expanded_workflow_profile_characterization": {
                    "barrier_label_coverage_rate_pct": 100.0,
                    "surface_fix_only_explained_rate_pct": 100.0,
                    "unresolved_explained_rate_pct": 100.0,
                    "profile_barrier_unclassified_count": 0,
                },
            }
            v093_path = root / "bad_v093_closeout.json"
            v093_path.write_text(json.dumps(bad_payload), encoding="utf-8")
            payload = build_v094_closeout(
                v093_closeout_path=str(v093_path),
                out_dir=str(root / "closeout"),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                threshold_input_table_path=str(root / "inputs" / "summary.json"),
                expanded_threshold_pack_path=str(root / "pack" / "summary.json"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_4_handoff_threshold_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
