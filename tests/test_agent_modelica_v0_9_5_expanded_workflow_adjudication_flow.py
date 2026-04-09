from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_9_5_adjudication_input_table import build_v095_adjudication_input_table
from gateforge.agent_modelica_v0_9_5_closeout import build_v095_closeout
from gateforge.agent_modelica_v0_9_5_expanded_workflow_adjudication import build_v095_expanded_workflow_adjudication
from gateforge.agent_modelica_v0_9_5_handoff_integrity import build_v095_handoff_integrity


class AgentModelicaV095ExpandedWorkflowAdjudicationFlowTests(unittest.TestCase):
    def _write_upstream_chain(self, root: Path) -> tuple[Path, Path, Path, Path]:
        v094_closeout = {
            "conclusion": {
                "version_decision": "v0_9_4_expanded_workflow_thresholds_frozen",
                "baseline_classification_under_frozen_pack": "expanded_workflow_readiness_partial_but_interpretable",
                "anti_tautology_pass": True,
                "integer_safe_pass": True,
                "threshold_ordering_pass": True,
                "execution_posture_pass": True,
                "v0_9_5_handoff_mode": "adjudicate_expanded_workflow_readiness_against_frozen_thresholds",
            }
        }
        v094_input = {
            "frozen_baseline_metrics": {
                "task_count": 19,
                "execution_source": "frozen_expanded_substrate_deterministic_replay",
                "workflow_resolution_case_count": 4,
                "goal_alignment_case_count": 9,
                "surface_fix_only_case_count": 5,
                "unresolved_case_count": 10,
                "goal_artifact_missing_after_surface_fix_case_count": 5,
                "dispatch_or_policy_limited_case_count": 5,
                "workflow_spillover_case_count": 5,
                "profile_barrier_unclassified_count": 0,
                "barrier_label_coverage_rate_pct": 100.0,
                "surface_fix_only_explained_rate_pct": 100.0,
                "unresolved_explained_rate_pct": 100.0,
                "profile_run_count": 3,
                "unexplained_case_flip_count": 0,
                "per_case_outcome_consistency_rate_pct": 100.0,
            }
        }
        v094_pack = {
            "supported_threshold_pack": {
                "primary_workflow_metrics": {
                    "workflow_resolution_case_count_min": 6,
                    "goal_alignment_case_count_min": 11,
                    "surface_fix_only_case_count_max": 5,
                    "unresolved_case_count_max": 8,
                },
                "barrier_sidecar_metrics": {
                    "workflow_spillover_case_count_max": 4,
                    "dispatch_or_policy_limited_case_count_max": 5,
                    "goal_artifact_missing_after_surface_fix_case_count_max": 5,
                    "profile_barrier_unclassified_count_max": 0,
                },
                "interpretability_safeguards": {
                    "barrier_label_coverage_rate_pct_min": 100.0,
                    "surface_fix_only_explained_rate_pct_min": 100.0,
                    "unresolved_explained_rate_pct_min": 100.0,
                },
                "repeatability_preconditions": {
                    "profile_run_count_min": 3,
                    "unexplained_case_flip_count_max": 1,
                    "per_case_outcome_consistency_rate_pct_min": 95.0,
                },
                "execution_posture": {
                    "allowed_execution_source": "frozen_expanded_substrate_deterministic_replay",
                    "scope_note": "fixture",
                },
            },
            "partial_threshold_pack": {
                "primary_workflow_metrics": {
                    "workflow_resolution_case_count_min": 4,
                    "goal_alignment_case_count_min": 9,
                    "surface_fix_only_case_count_max": 6,
                    "unresolved_case_count_max": 10,
                },
                "barrier_sidecar_metrics": {
                    "workflow_spillover_case_count_max": 5,
                    "dispatch_or_policy_limited_case_count_max": 5,
                    "goal_artifact_missing_after_surface_fix_case_count_max": 5,
                    "profile_barrier_unclassified_count_max": 0,
                },
                "interpretability_safeguards": {
                    "barrier_label_coverage_rate_pct_min": 100.0,
                    "surface_fix_only_explained_rate_pct_min": 100.0,
                    "unresolved_explained_rate_pct_min": 100.0,
                },
                "repeatability_preconditions": {
                    "profile_run_count_min": 3,
                    "unexplained_case_flip_count_max": 1,
                    "per_case_outcome_consistency_rate_pct_min": 95.0,
                },
                "execution_posture": {
                    "allowed_execution_source": "frozen_expanded_substrate_deterministic_replay",
                    "scope_note": "fixture",
                },
            },
            "fallback_rule_summary": {
                "fallback_trigger_semantics": [
                    "workflow_resolved_core_too_low_for_interpretable_band",
                    "goal_alignment_core_too_low_for_interpretable_band",
                    "barrier_explainability_guard_failed",
                    "repeatability_precondition_failed",
                    "execution_posture_semantics_mismatch",
                ]
            },
        }
        v093_closeout = {
            "expanded_profile_replay_pack": {
                "execution_source": "frozen_expanded_substrate_deterministic_replay",
            },
            "expanded_workflow_profile_characterization": {
                "profile_barrier_unclassified_count": 0,
                "barrier_label_distribution": {
                    "goal_artifact_missing_after_surface_fix": 5,
                    "dispatch_or_policy_limited_unresolved": 5,
                    "workflow_spillover_unresolved": 5,
                },
            },
        }
        v094_closeout_path = root / "v094_closeout.json"
        v094_input_path = root / "v094_input.json"
        v094_pack_path = root / "v094_pack.json"
        v093_closeout_path = root / "v093_closeout.json"
        v094_closeout_path.write_text(json.dumps(v094_closeout), encoding="utf-8")
        v094_input_path.write_text(json.dumps(v094_input), encoding="utf-8")
        v094_pack_path.write_text(json.dumps(v094_pack), encoding="utf-8")
        v093_closeout_path.write_text(json.dumps(v093_closeout), encoding="utf-8")
        return v094_closeout_path, v094_input_path, v094_pack_path, v093_closeout_path

    def test_handoff_integrity_passes_on_frozen_threshold_pack(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v094_closeout_path, _, _, _ = self._write_upstream_chain(root)
            payload = build_v095_handoff_integrity(
                v094_closeout_path=str(v094_closeout_path),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(
                payload["baseline_classification_under_frozen_pack"],
                "expanded_workflow_readiness_partial_but_interpretable",
            )

    def test_adjudication_input_table_collects_frozen_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, v094_input_path, v094_pack_path, v093_closeout_path = self._write_upstream_chain(root)
            payload = build_v095_adjudication_input_table(
                v093_closeout_path=str(v093_closeout_path),
                v094_threshold_input_table_path=str(v094_input_path),
                v094_expanded_threshold_pack_path=str(v094_pack_path),
                out_dir=str(root / "inputs"),
            )
            self.assertEqual(payload["frozen_baseline_metrics"]["workflow_resolution_case_count"], 4)
            self.assertTrue(payload["execution_posture_compatibility"]["compatible"])

    def test_expanded_workflow_adjudication_observes_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, v094_input_path, v094_pack_path, v093_closeout_path = self._write_upstream_chain(root)
            build_v095_adjudication_input_table(
                v093_closeout_path=str(v093_closeout_path),
                v094_threshold_input_table_path=str(v094_input_path),
                v094_expanded_threshold_pack_path=str(v094_pack_path),
                out_dir=str(root / "inputs"),
            )
            payload = build_v095_expanded_workflow_adjudication(
                adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                v093_closeout_path=str(v093_closeout_path),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(
                payload["final_adjudication_label"],
                "expanded_workflow_readiness_partial_but_interpretable",
            )
            self.assertEqual(payload["adjudication_route_count"], 1)

    def test_supported_path_is_executable_with_stronger_synthetic_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, v094_input_path, v094_pack_path, v093_closeout_path = self._write_upstream_chain(root)
            strong_metrics = json.loads(v094_input_path.read_text())
            strong_metrics["frozen_baseline_metrics"]["workflow_resolution_case_count"] = 6
            strong_metrics["frozen_baseline_metrics"]["goal_alignment_case_count"] = 11
            strong_metrics["frozen_baseline_metrics"]["unresolved_case_count"] = 8
            strong_metrics["frozen_baseline_metrics"]["workflow_spillover_case_count"] = 4
            strong_metrics_path = root / "strong_input.json"
            strong_metrics_path.write_text(json.dumps(strong_metrics), encoding="utf-8")
            payload = build_v095_adjudication_input_table(
                v093_closeout_path=str(v093_closeout_path),
                v094_threshold_input_table_path=str(strong_metrics_path),
                v094_expanded_threshold_pack_path=str(v094_pack_path),
                out_dir=str(root / "inputs"),
            )
            verdict = build_v095_expanded_workflow_adjudication(
                adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                v093_closeout_path=str(v093_closeout_path),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(verdict["final_adjudication_label"], "expanded_workflow_readiness_supported")

    def test_fallback_path_is_executable_with_weaker_synthetic_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, v094_input_path, v094_pack_path, v093_closeout_path = self._write_upstream_chain(root)
            weak_metrics = json.loads(v094_input_path.read_text())
            weak_metrics["frozen_baseline_metrics"]["workflow_resolution_case_count"] = 3
            weak_metrics["frozen_baseline_metrics"]["goal_alignment_case_count"] = 8
            weak_metrics["frozen_baseline_metrics"]["unresolved_case_count"] = 11
            weak_metrics_path = root / "weak_input.json"
            weak_metrics_path.write_text(json.dumps(weak_metrics), encoding="utf-8")
            build_v095_adjudication_input_table(
                v093_closeout_path=str(v093_closeout_path),
                v094_threshold_input_table_path=str(weak_metrics_path),
                v094_expanded_threshold_pack_path=str(v094_pack_path),
                out_dir=str(root / "inputs"),
            )
            verdict = build_v095_expanded_workflow_adjudication(
                adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                v093_closeout_path=str(v093_closeout_path),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(
                verdict["final_adjudication_label"],
                "fallback_to_profile_clarification_or_expansion_needed",
            )

    def test_closeout_reaches_partial_but_interpretable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v094_closeout_path, v094_input_path, v094_pack_path, v093_closeout_path = self._write_upstream_chain(root)
            payload = build_v095_closeout(
                v094_closeout_path=str(v094_closeout_path),
                v094_threshold_input_table_path=str(v094_input_path),
                v094_expanded_threshold_pack_path=str(v094_pack_path),
                v093_closeout_path=str(v093_closeout_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                expanded_workflow_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_9_5_expanded_workflow_readiness_partial_but_interpretable",
            )
            self.assertEqual(
                payload["conclusion"]["v0_9_6_handoff_mode"],
                "decide_whether_more_authentic_expansion_is_still_worth_it",
            )

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_v094 = {
                "conclusion": {
                    "version_decision": "v0_9_4_expanded_workflow_thresholds_partial",
                    "baseline_classification_under_frozen_pack": "expanded_workflow_readiness_partial_but_interpretable",
                    "anti_tautology_pass": True,
                    "integer_safe_pass": True,
                    "threshold_ordering_pass": True,
                    "execution_posture_pass": True,
                    "v0_9_5_handoff_mode": "clarify_threshold_pack_before_adjudication",
                }
            }
            bad_v094_path = root / "bad_v094_closeout.json"
            bad_v094_path.write_text(json.dumps(bad_v094), encoding="utf-8")
            _, v094_input_path, v094_pack_path, v093_closeout_path = self._write_upstream_chain(root)
            payload = build_v095_closeout(
                v094_closeout_path=str(bad_v094_path),
                v094_threshold_input_table_path=str(v094_input_path),
                v094_expanded_threshold_pack_path=str(v094_pack_path),
                v093_closeout_path=str(v093_closeout_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                expanded_workflow_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_9_5_adjudication_inputs_invalid",
            )


if __name__ == "__main__":
    unittest.main()
