from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_expected_actual_delta_attribution_v0_35_35 import (
    build_expected_actual_delta_attribution,
)


class ExpectedActualDeltaAttributionV03535Tests(unittest.TestCase):
    def test_detects_expected_actual_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": "sem_x",
                "final_verdict": "FAILED",
                "steps": [
                    {
                        "step": 1,
                        "tool_calls": [
                            {
                                "name": "record_repair_hypothesis",
                                "arguments": {"expected_equation_delta": 2},
                            }
                        ],
                    },
                    {"step": 2, "tool_calls": [{"name": "residual_hypothesis_consistency_check"}]},
                    {
                        "step": 3,
                        "tool_calls": [
                            {
                                "name": "check_model",
                                "arguments": {
                                    "model_text": "model X equation for i in 1:2 loop p[i].i = 0; n[i].i = 0; end for; end X;"
                                },
                            }
                        ],
                    },
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_expected_actual_delta_attribution(
                run_dirs=[run_dir],
                target_case_ids=["sem_x"],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["mismatch_count"], 1)

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_expected_actual_delta_attribution(
                run_dirs=[root / "missing"],
                target_case_ids=["sem_x"],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
