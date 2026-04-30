from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_preference_live_attribution_v0_35_29 import (
    build_candidate_preference_live_attribution,
)
from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import TARGET_CASE_ID


class CandidatePreferenceLiveAttributionV03529Tests(unittest.TestCase):
    def test_detects_compiler_preference_without_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            preference = {
                "compiler_evidence_preferred": True,
                "selected_expected_equation_delta": 4,
                "rejected_expected_equation_delta": 6,
            }
            row = {
                "case_id": TARGET_CASE_ID,
                "final_verdict": "FAILED",
                "submitted": False,
                "steps": [
                    {
                        "step": 1,
                        "tool_results": [
                            {
                                "name": "record_candidate_preference_rationale",
                                "result": json.dumps(preference),
                            }
                        ],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_candidate_preference_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["decision"], "compiler_preference_recorded_without_test")

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_candidate_preference_live_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
