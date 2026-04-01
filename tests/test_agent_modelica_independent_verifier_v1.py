from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_independent_verifier_v1 import (
    verify_branch_switch_frontier_flow_v0_3_7,
    verify_branch_switch_forcing_flow_v0_3_8,
    verify_post_restore_evidence_flow,
    verify_post_restore_frontier_flow_v0_3_6,
    verify_v0_3_10_continuity_flow,
)


class AgentModelicaIndependentVerifierV1Tests(unittest.TestCase):
    def test_verify_post_restore_evidence_flow_passes_on_aligned_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_independent_verifier_v1_") as td:
            root = Path(td)
            lane = root / "lane.json"
            run = root / "run.json"
            promotion = root / "promotion.json"
            classifier = root / "classifier.json"
            lane.write_text(json.dumps({"lane_status": "FREEZE_READY"}), encoding="utf-8")
            run.write_text(
                json.dumps(
                    {
                        "total": 2,
                        "passed": 2,
                        "deterministic_only_pct": 0.0,
                        "results": [
                            {"task_id": "a", "resolution_path": "rule_then_llm"},
                            {"task_id": "b", "resolution_path": "rule_then_llm"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            promotion.write_text(
                json.dumps(
                    {
                        "status": "PROMOTION_READY",
                        "observed_metrics": {
                            "total_cases": 2,
                            "passed_cases": 2,
                            "rule_then_llm_count": 2,
                            "deterministic_only_pct": 0.0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 2,
                            "failure_bucket_counts": {"success_after_restore": 2},
                        }
                    }
                ),
                encoding="utf-8",
            )
            payload = verify_post_restore_evidence_flow(
                lane_summary_path=str(lane),
                run_summary_path=str(run),
                promotion_summary_path=str(promotion),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "PASS")
        self.assertEqual((payload.get("summary") or {}).get("failed_checks"), [])

    def test_verify_post_restore_evidence_flow_fails_on_misaligned_counts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_independent_verifier_v1_fail_") as td:
            root = Path(td)
            lane = root / "lane.json"
            run = root / "run.json"
            promotion = root / "promotion.json"
            classifier = root / "classifier.json"
            lane.write_text(json.dumps({"lane_status": "FREEZE_READY"}), encoding="utf-8")
            run.write_text(json.dumps({"total": 2, "passed": 1, "results": []}), encoding="utf-8")
            promotion.write_text(json.dumps({"status": "PROMOTION_READY", "observed_metrics": {"total_cases": 3, "passed_cases": 1, "rule_then_llm_count": 0, "deterministic_only_pct": 0.0}}), encoding="utf-8")
            classifier.write_text(json.dumps({"metrics": {"total_rows": 2, "failure_bucket_counts": {"success_after_restore": 1}}}), encoding="utf-8")
            payload = verify_post_restore_evidence_flow(
                lane_summary_path=str(lane),
                run_summary_path=str(run),
                promotion_summary_path=str(promotion),
                classifier_summary_path=str(classifier),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "FAIL")
        self.assertIn("counts_align_across_summaries", (payload.get("summary") or {}).get("failed_checks") or [])

    def test_verify_post_restore_frontier_flow_v0_3_6_passes_on_aligned_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_independent_verifier_v1_v036_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            dev = root / "dev.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "lane_summary": {
                            "total_candidate_count": 3,
                            "composition": {"single_sweep_success_rate_pct": 33.3},
                        }
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 3,
                            "success_beyond_single_sweep_count": 2,
                            "failure_bucket_counts": {
                                "stalled_search_after_progress": 1,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            dev.write_text(
                json.dumps(
                    {
                        "primary_harder_direction": {"operator": "paired_value_collapse"},
                        "next_bottleneck": {"lever": "guided_replan_after_progress"},
                        "deterministic_coverage_explanation": {"present": True},
                    }
                ),
                encoding="utf-8",
            )
            payload = verify_post_restore_frontier_flow_v0_3_6(
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                dev_priorities_summary_path=str(dev),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "PASS")
        self.assertEqual((payload.get("summary") or {}).get("failed_checks"), [])

    def test_verify_post_restore_frontier_flow_v0_3_6_fails_when_bucket_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_independent_verifier_v1_v036_fail_") as td:
            root = Path(td)
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            dev = root / "dev.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "lane_summary": {
                            "total_candidate_count": 2,
                            "composition": {"single_sweep_success_rate_pct": 0.0},
                        }
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 2,
                            "success_beyond_single_sweep_count": 0,
                            "failure_bucket_counts": {},
                        }
                    }
                ),
                encoding="utf-8",
            )
            dev.write_text(
                json.dumps(
                    {
                        "primary_harder_direction": {"operator": "paired_value_collapse"},
                        "next_bottleneck": {"lever": "guided_replan_after_progress"},
                        "deterministic_coverage_explanation": {"present": False},
                    }
                ),
                encoding="utf-8",
            )
            payload = verify_post_restore_frontier_flow_v0_3_6(
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                dev_priorities_summary_path=str(dev),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "FAIL")
        self.assertIn("next_bottleneck_has_supporting_bucket", (payload.get("summary") or {}).get("failed_checks") or [])

    def test_verify_branch_switch_frontier_flow_v0_3_7_passes_on_aligned_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_independent_verifier_v1_v037_") as td:
            root = Path(td)
            lane = root / "lane.json"
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            dev = root / "dev.json"
            lane.write_text(json.dumps({"lane_status": "CANDIDATE_READY"}), encoding="utf-8")
            refreshed.write_text(
                json.dumps(
                    {
                        "metrics": {"total_rows": 2},
                        "tasks": [
                            {"task_id": "a", "baseline_measurement_protocol": {"protocol_version": "x"}},
                            {"task_id": "b", "baseline_measurement_protocol": {"protocol_version": "x"}},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 2,
                            "failure_bucket_counts": {"stalled_search_after_progress": 2},
                        }
                    }
                ),
                encoding="utf-8",
            )
            dev.write_text(
                json.dumps(
                    {
                        "primary_replan_direction": {"family_id": "post_restore_branch_switch_after_stall"},
                        "next_bottleneck": {"lever": "branch_switch_replan_after_stall"},
                    }
                ),
                encoding="utf-8",
            )
            payload = verify_branch_switch_frontier_flow_v0_3_7(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                dev_priorities_summary_path=str(dev),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "PASS")
        self.assertEqual((payload.get("summary") or {}).get("failed_checks"), [])

    def test_verify_branch_switch_forcing_flow_v0_3_8_passes_on_aligned_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_independent_verifier_v1_v038_") as td:
            root = Path(td)
            lane = root / "lane.json"
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            dev = root / "dev.json"
            lane.write_text(json.dumps({"lane_status": "CANDIDATE_READY"}), encoding="utf-8")
            refreshed.write_text(
                json.dumps(
                    {
                        "metrics": {"total_rows": 2},
                        "tasks": [
                            {
                                "task_id": "a",
                                "baseline_measurement_protocol": {"protocol_version": "x"},
                                "success_after_branch_switch": True,
                                "success_without_branch_switch_evidence": False,
                            },
                            {
                                "task_id": "b",
                                "baseline_measurement_protocol": {"protocol_version": "x"},
                                "success_after_branch_switch": False,
                                "success_without_branch_switch_evidence": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "bucket_schema_version": "v0_3_8_branch_switch_primary_buckets_v1",
                        "frozen_mainline_task_ids": ["a", "b"],
                        "metrics": {
                            "total_rows": 2,
                            "failure_bucket_counts": {
                                "success_after_branch_switch": 1,
                                "success_without_branch_switch_evidence": 1,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            dev.write_text(
                json.dumps(
                    {
                        "primary_direction": {"family_id": "post_restore_explicit_branch_switch_after_stall"},
                    }
                ),
                encoding="utf-8",
            )
            payload = verify_branch_switch_forcing_flow_v0_3_8(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                dev_priorities_summary_path=str(dev),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "PASS")
        self.assertEqual((payload.get("summary") or {}).get("failed_checks"), [])

    def test_verify_v0_3_10_continuity_flow_passes_on_aligned_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_independent_verifier_v1_v0310_") as td:
            root = Path(td)
            lane = root / "lane.json"
            refreshed = root / "refreshed.json"
            classifier = root / "classifier.json"
            decision = root / "decision.json"
            lane.write_text(json.dumps({"family_id": "same_branch_continuity_after_partial_progress"}), encoding="utf-8")
            refreshed.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 3,
                            "successful_case_count": 3,
                            "success_after_same_branch_continuation_count": 0,
                            "success_with_explicit_branch_switch_evidence_pct": 0.0,
                        }
                    }
                ),
                encoding="utf-8",
            )
            classifier.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "total_rows": 3,
                            "primary_bucket_counts": {
                                "true_same_branch_multi_step_success": 0,
                                "same_branch_one_shot_or_accidental_success": 3,
                                "hidden_branch_change_misclassified_as_continuity": 0,
                                "stalled_unresolved_same_branch_failure": 0,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            decision.write_text(json.dumps({"decision": "narrower_replacement_hypothesis_supported"}), encoding="utf-8")
            payload = verify_v0_3_10_continuity_flow(
                lane_summary_path=str(lane),
                refreshed_summary_path=str(refreshed),
                classifier_summary_path=str(classifier),
                block_b_decision_summary_path=str(decision),
                out_dir=str(root / "out"),
            )
        self.assertEqual(payload.get("status"), "PASS")
        self.assertEqual((payload.get("summary") or {}).get("failed_checks"), [])
