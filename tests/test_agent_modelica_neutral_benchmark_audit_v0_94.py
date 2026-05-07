from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from gateforge.agent_modelica_neutral_benchmark_audit_v0_94_0 import (
    audit_text,
    audit_task_jsonl,
    build_neutral_benchmark_audit,
)


class NeutralBenchmarkAuditV094Tests(unittest.TestCase):
    def test_audit_text_flags_visible_repair_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompt.py"
            path.write_text("Tell the LLM to use p.i = 0 as the fix.", encoding="utf-8")

            row = audit_text(path)

        self.assertEqual(row["status"], "REVIEW")
        self.assertEqual(row["hits"][0]["phrase"], "p.i = 0")

    def test_current_neutral_paths_have_no_visible_repair_hints(self) -> None:
        summary = build_neutral_benchmark_audit()

        self.assertEqual(summary["status"], "PASS")
        self.assertTrue(summary["conclusion_allowed"])
        self.assertEqual(summary["review_path_count"], 0)
        self.assertEqual(summary["review_task_path_count"], 0)

    def test_task_audit_checks_only_visible_prompt_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tasks.jsonl"
            rows = [
                {
                    "case_id": "hidden_ok",
                    "description": "Repair the model while preserving outputs.",
                    "constraints": ["Submit only after OMC passes."],
                    "hidden_oracle": {"reference_repair_summary": "p.i = 0"},
                },
                {
                    "case_id": "visible_bad",
                    "description": "The correct fix is p.i = 0.",
                    "constraints": [],
                },
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            summary = audit_task_jsonl(path)

        self.assertEqual(summary["status"], "REVIEW")
        self.assertEqual(summary["review_row_count"], 1)
        self.assertEqual(summary["review_rows"][0]["case_id"], "visible_bad")


if __name__ == "__main__":
    unittest.main()
