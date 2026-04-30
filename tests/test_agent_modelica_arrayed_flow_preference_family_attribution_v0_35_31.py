from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_arrayed_flow_preference_family_attribution_v0_35_31 import (
    build_arrayed_flow_preference_family_attribution,
)


class ArrayedFlowPreferenceFamilyAttributionV03531Tests(unittest.TestCase):
    def test_family_level_failure_when_mixed_results_and_preference_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            rows = [
                {
                    "case_id": "sem_a",
                    "final_verdict": "PASS",
                    "submitted": True,
                    "steps": [],
                },
                {
                    "case_id": "sem_b",
                    "final_verdict": "FAILED",
                    "submitted": False,
                    "steps": [
                        {
                            "step": 1,
                            "tool_calls": [
                                {
                                    "name": "record_equation_delta_candidate_portfolio",
                                    "arguments": {
                                        "compiler_named_residual_count": 4,
                                        "candidates": [
                                            {"strategy": "a", "expected_equation_delta": 4, "rationale": "r"}
                                        ],
                                        "selected_strategy": "a",
                                    },
                                }
                            ],
                            "tool_results": [
                                {
                                    "name": "record_candidate_preference_rationale",
                                    "result": json.dumps({"compiler_evidence_preferred": False}),
                                }
                            ],
                        }
                    ],
                },
            ]
            (run_dir / "results.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            summary = build_arrayed_flow_preference_family_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["pass_count"], 1)
            self.assertEqual(summary["preference_used_count"], 1)
            self.assertEqual(summary["decision"], "arrayed_flow_preference_failure_is_family_level_not_sem22_only")

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_arrayed_flow_preference_family_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
