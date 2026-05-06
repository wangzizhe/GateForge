from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_medium_hard_training_trace_v0_80_0 import (
    build_medium_hard_training_trace_summary,
)


class MediumHardTrainingTraceV080Tests(unittest.TestCase):
    def test_build_training_trace_marks_submit_decision_supervision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            tasks.write_text(json.dumps({"case_id": "case_a", "registry_family": "f"}) + "\n", encoding="utf-8")
            low = root / "low.jsonl"
            high = root / "high.jsonl"
            low.write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "final_verdict": "FAILED",
                        "submitted": False,
                        "candidate_files": [{"candidate_id": "c1", "write_check_ok": True, "write_simulate_ok": True}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            high.write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "final_verdict": "PASS",
                        "submitted": True,
                        "candidate_files": [{"candidate_id": "c2", "write_check_ok": True, "write_simulate_ok": True}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            summary = build_medium_hard_training_trace_summary(
                tasks_path=tasks,
                result_paths_by_arm={"budget_32k": low, "budget_64k": high},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["training_schema_ready"])
            self.assertFalse(summary["training_data_ready"])
            self.assertEqual(summary["arm_taxonomy_counts"]["successful_candidate_not_submitted"], 1)
            self.assertEqual(summary["arm_taxonomy_counts"]["solved_submitted"], 1)
            self.assertEqual(summary["learning_role_counts"]["submit_decision_supervision_candidate"], 1)
            self.assertEqual(summary["learning_role_counts"]["budget_sensitive_positive_transition"], 1)
            self.assertEqual(summary["submit_decision_signal_case_count"], 1)
            self.assertEqual(summary["substrate_interpretation"], "submit_decision_signal_present_in_all_cases")

    def test_build_training_trace_marks_negative_only_generation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            tasks.write_text(json.dumps({"case_id": "case_a", "registry_family": "f"}) + "\n", encoding="utf-8")
            low = root / "low.jsonl"
            high = root / "high.jsonl"
            row = {"case_id": "case_a", "final_verdict": "FAILED", "candidate_files": []}
            low.write_text(json.dumps(row) + "\n", encoding="utf-8")
            high.write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_medium_hard_training_trace_summary(
                tasks_path=tasks,
                result_paths_by_arm={"budget_32k": low, "budget_64k": high},
                out_dir=root / "out",
            )
            self.assertEqual(summary["arm_taxonomy_counts"]["candidate_generation_failure"], 2)
            self.assertEqual(summary["learning_role_counts"]["candidate_generation_negative_only"], 1)
            self.assertEqual(summary["negative_only_generation_case_count"], 1)
            trace = json.loads((root / "out" / "training_traces.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(trace["supervision_status"], "negative_only")


if __name__ == "__main__":
    unittest.main()
