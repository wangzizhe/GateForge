from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_implementation_live_attribution_v0_35_36 import (
    build_candidate_implementation_live_attribution,
)


class CandidateImplementationLiveAttributionV03536Tests(unittest.TestCase):
    def test_detects_mismatch_without_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            payload = {
                "implementation_matches_expected_delta": False,
                "implemented_zero_flow_equation_count": 4,
                "expected_equation_delta": 2,
            }
            row = {
                "case_id": "sem_x",
                "final_verdict": "FAILED",
                "submitted": False,
                "steps": [
                    {
                        "step": 1,
                        "tool_results": [
                            {
                                "name": "candidate_implementation_consistency_check",
                                "result": json.dumps(payload),
                            }
                        ],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_candidate_implementation_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "implementation_mismatch_detected_without_recovery")

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_candidate_implementation_live_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
