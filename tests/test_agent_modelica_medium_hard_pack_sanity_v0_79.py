from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_medium_hard_pack_sanity_v0_79_0 import build_medium_hard_pack_sanity_summary


class MediumHardPackSanityV079Tests(unittest.TestCase):
    def test_build_medium_hard_pack_sanity_summary_reports_paired_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            tasks.write_text(
                "\n".join(
                    [
                        json.dumps({"case_id": "case_a", "registry_family": "f"}),
                        json.dumps({"case_id": "case_b", "registry_family": "f"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            low = root / "low.jsonl"
            high = root / "high.jsonl"
            low.write_text(
                "\n".join(
                    [
                        json.dumps({"case_id": "case_a", "final_verdict": "FAILED", "candidate_files": []}),
                        json.dumps({"case_id": "case_b", "final_verdict": "PASS", "candidate_files": [{}]}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            high.write_text(
                "\n".join(
                    [
                        json.dumps({"case_id": "case_a", "final_verdict": "PASS", "candidate_files": [{}]}),
                        json.dumps({"case_id": "case_b", "final_verdict": "PASS", "candidate_files": [{}]}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = build_medium_hard_pack_sanity_summary(
                tasks_path=tasks,
                result_paths_by_arm={"budget_32k": low, "budget_64k": high},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["reporting_conclusion_allowed"])
            self.assertFalse(summary["capability_conclusion_allowed"])
            self.assertEqual(summary["pass_counts_by_arm"], {"budget_32k": 1, "budget_64k": 2})
            self.assertEqual(summary["paired_status_counts"]["all_pass"], 1)
            self.assertEqual(summary["paired_status_counts"]["split_budget_64k_only"], 1)

    def test_build_medium_hard_pack_sanity_summary_blocks_missing_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            tasks.write_text(json.dumps({"case_id": "case_a", "registry_family": "f"}) + "\n", encoding="utf-8")
            low = root / "low.jsonl"
            high = root / "high.jsonl"
            low.write_text("", encoding="utf-8")
            high.write_text(json.dumps({"case_id": "case_a", "final_verdict": "PASS"}) + "\n", encoding="utf-8")
            summary = build_medium_hard_pack_sanity_summary(
                tasks_path=tasks,
                result_paths_by_arm={"budget_32k": low, "budget_64k": high},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")
            self.assertFalse(summary["artifact_complete"])
            self.assertEqual(summary["missing_by_arm"]["budget_32k"], ["case_a"])


if __name__ == "__main__":
    unittest.main()
