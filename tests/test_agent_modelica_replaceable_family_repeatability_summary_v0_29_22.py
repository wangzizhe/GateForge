from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_replaceable_family_repeatability_summary_v0_29_22 import (
    build_replaceable_family_repeatability_summary,
)


def _write_run(path: Path, *, verdict: str, submitted: bool, successful_tool: bool) -> None:
    path.mkdir(parents=True)
    tool_result = 'resultFile = "/workspace/X_res.mat"' if successful_tool else 'Failed to build model'
    row = {
        "case_id": "sem_case",
        "final_verdict": verdict,
        "submitted": submitted,
        "token_used": 1000,
        "steps": [
            {
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}],
                "tool_results": [{"name": "check_model", "result": tool_result}],
            }
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ReplaceableFamilyRepeatabilitySummaryV02922Tests(unittest.TestCase):
    def test_build_summary_reports_submission_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_1 = root / "run_1"
            run_2 = root / "run_2"
            _write_run(run_1, verdict="PASS", submitted=True, successful_tool=True)
            _write_run(run_2, verdict="FAILED", submitted=False, successful_tool=True)
            summary = build_replaceable_family_repeatability_summary(
                run_dirs=[run_1, run_2],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "family_roles_mixed_with_submission_discipline_issue")
            self.assertEqual(summary["submission_discipline_issue_count"], 1)
            self.assertTrue(summary["cases"][0]["submission_discipline_issue"])
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
