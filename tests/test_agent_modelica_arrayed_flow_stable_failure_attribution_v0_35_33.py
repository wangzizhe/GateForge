from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_arrayed_flow_stable_failure_attribution_v0_35_33 import (
    build_arrayed_flow_stable_failure_attribution,
)


class ArrayedFlowStableFailureAttributionV03533Tests(unittest.TestCase):
    def test_detects_heterogeneous_stable_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            candidate = root / "candidate"
            base.mkdir()
            candidate.mkdir()
            base_rows = [
                {"case_id": "a", "final_verdict": "FAILED", "steps": []},
                {"case_id": "b", "final_verdict": "FAILED", "steps": []},
            ]
            candidate_rows = [
                {
                    "case_id": "a",
                    "final_verdict": "FAILED",
                    "steps": [
                        {
                            "step": 1,
                            "tool_calls": [
                                {
                                    "name": "record_equation_delta_candidate_portfolio",
                                    "arguments": {
                                        "compiler_named_residual_count": 2,
                                        "candidates": [
                                            {"strategy": "x", "expected_equation_delta": 2, "rationale": "r"}
                                        ],
                                        "selected_strategy": "x",
                                    },
                                }
                            ],
                        }
                    ],
                },
                {
                    "case_id": "b",
                    "final_verdict": "FAILED",
                    "steps": [
                        {"step": 1, "tool_calls": [{"name": "residual_hypothesis_consistency_check"}]},
                        {
                            "step": 2,
                            "tool_calls": [
                                {"name": "check_model", "arguments": {"model_text": "model X equation p.i = 0; end X;"}}
                            ],
                        },
                    ],
                },
            ]
            (base / "results.jsonl").write_text("\n".join(json.dumps(row) for row in base_rows) + "\n")
            (candidate / "results.jsonl").write_text(
                "\n".join(json.dumps(row) for row in candidate_rows) + "\n"
            )
            summary = build_arrayed_flow_stable_failure_attribution(
                base_dir=base,
                candidate_dir=candidate,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "stable_failures_are_family_level_but_heterogeneous")

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_arrayed_flow_stable_failure_attribution(
                base_dir=root / "missing_base",
                candidate_dir=root / "missing_candidate",
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
