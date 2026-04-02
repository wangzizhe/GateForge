from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_12_one_shot_classifier import (
    build_v0_3_12_one_shot_classifier,
    classify_one_shot_case,
)


class AgentModelicaV0312OneShotClassifierTests(unittest.TestCase):
    def test_classifies_one_shot_when_planner_event_count_eq_1(self) -> None:
        payload = classify_one_shot_case(
            row={
                "task_id": "one",
                "verdict": "PASS",
                "executor_runtime_hygiene": {"planner_event_count": 1},
            }
        )
        self.assertEqual(payload["label"], "one_shot")
        self.assertEqual(payload["reason"], "planner_event_count_eq_1")

    def test_returns_unknown_when_required_signals_are_missing(self) -> None:
        payload = classify_one_shot_case(
            row={
                "task_id": "unknown",
                "verdict": "PASS",
            }
        )
        self.assertEqual(payload["label"], "unknown")
        self.assertIn("planner_event_count_missing", payload["reason"])
        self.assertIn("detected_branch_sequence_missing", payload["reason"])
        self.assertIn("attempts_missing_or_lt_2", payload["reason"])

    def test_classifies_true_continuity_for_multi_planner_same_branch_with_progress(self) -> None:
        payload = classify_one_shot_case(
            row={
                "task_id": "continuity",
                "verdict": "PASS",
                "executor_runtime_hygiene": {"planner_event_count": 2},
                "detected_branch_sequence": ["continue_on_m", "continue_on_m"],
            },
            detail={
                "attempts": [
                    {"round": 1, "check_model_pass": True, "simulate_pass": False},
                    {"round": 2, "check_model_pass": True, "simulate_pass": True},
                ]
            },
        )
        self.assertEqual(payload["label"], "true_continuity")
        self.assertEqual(payload["reason"], "planner_ge_2_single_branch_progress_seen")
        self.assertEqual(len(payload["audit"]["progress_signal_pairs"]), 1)

    def test_classifies_multi_step_non_continuity_when_branch_resets(self) -> None:
        payload = classify_one_shot_case(
            row={
                "task_id": "branch-reset",
                "verdict": "PASS",
                "executor_runtime_hygiene": {"planner_event_count": 2},
                "detected_branch_sequence": ["continue_on_m", "switch_to_d"],
            },
            detail={
                "attempts": [
                    {"round": 1, "check_model_pass": True, "simulate_pass": False},
                    {"round": 2, "check_model_pass": True, "simulate_pass": True},
                ]
            },
        )
        self.assertEqual(payload["label"], "multi_step_non_continuity")
        self.assertIn("branch_sequence_not_single_value", payload["reason"])

    def test_labels_failed_rows_as_failed_or_unresolved(self) -> None:
        payload = classify_one_shot_case(
            row={
                "task_id": "fail",
                "verdict": "FAIL",
                "executor_runtime_hygiene": {"planner_event_count": 3},
            }
        )
        self.assertEqual(payload["label"], "failed_or_unresolved")
        self.assertFalse(payload["success"])

    def test_build_summary_counts_only_non_unknown_successes_as_labeled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result_one = root / "one.json"
            result_one.write_text(
                json.dumps(
                    {
                        "executor_runtime_hygiene": {"planner_event_count": 1},
                    }
                ),
                encoding="utf-8",
            )
            result_continuity = root / "continuity.json"
            result_continuity.write_text(
                json.dumps(
                    {
                        "executor_runtime_hygiene": {"planner_event_count": 2},
                        "attempts": [
                            {"round": 1, "check_model_pass": True, "simulate_pass": False},
                            {"round": 2, "check_model_pass": True, "simulate_pass": True},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result_unknown = root / "unknown.json"
            result_unknown.write_text(json.dumps({"attempts": []}), encoding="utf-8")
            refreshed = root / "refreshed.json"
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "one",
                                "verdict": "PASS",
                                "result_json_path": str(result_one),
                            },
                            {
                                "task_id": "continuity",
                                "verdict": "PASS",
                                "detected_branch_sequence": ["continue_on_m", "continue_on_m"],
                                "result_json_path": str(result_continuity),
                            },
                            {
                                "task_id": "unknown",
                                "verdict": "PASS",
                                "detected_branch_sequence": ["continue_on_m"],
                                "result_json_path": str(result_unknown),
                            },
                            {
                                "task_id": "fail",
                                "verdict": "FAIL",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_v0_3_12_one_shot_classifier(
                refreshed_summary_path=str(refreshed),
                out_dir=str(root / "out"),
            )
            metrics = payload["metrics"]
            self.assertEqual(metrics["successful_case_count"], 3)
            self.assertEqual(metrics["successful_labeled_count"], 2)
            self.assertEqual(metrics["unknown_success_count"], 1)
            self.assertEqual(metrics["true_continuity_count"], 1)
            self.assertEqual(metrics["true_continuity_pct"], 50.0)
            labeled = json.loads((root / "out" / "labeled_cases.json").read_text(encoding="utf-8"))
            self.assertEqual(len(labeled["rows"]), 4)


if __name__ == "__main__":
    unittest.main()
