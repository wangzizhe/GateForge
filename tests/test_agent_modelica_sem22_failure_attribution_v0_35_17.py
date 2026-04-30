from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_sem22_failure_attribution_v0_35_17 import (
    TARGET_CASE_ID,
    build_sem22_failure_attribution,
)


class Sem22FailureAttributionV03517Tests(unittest.TestCase):
    def test_build_summary_from_failed_arrayed_bus_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            diagnostic = {
                "connection_sets": [
                    {"member_count": 7, "members": ["rail", "branch[1].a", "probe.p[1]"]},
                ]
            }
            row = {
                "case_id": TARGET_CASE_ID,
                "tool_profile": "connector_flow_minimal_contract_checkpoint",
                "final_verdict": "FAILED",
                "submitted": False,
                "step_count": 3,
                "steps": [
                    {
                        "step": 2,
                        "tool_results": [
                            {
                                "name": "connector_flow_state_diagnostic",
                                "result": json.dumps(diagnostic),
                            }
                        ],
                    },
                    {
                        "step": 3,
                        "tool_results": [
                            {
                                "name": "record_repair_hypothesis",
                                "arguments": {"expected_equation_delta": 6},
                                "result": "{}",
                            }
                        ],
                    },
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_sem22_failure_attribution(run_dirs=[run_dir], out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["pass_count"], 0)
            self.assertEqual(summary["success_candidate_seen_count"], 0)
            self.assertEqual(summary["large_bus_observed_runs"], 1)
            self.assertEqual(summary["decision"], "sem22_failure_concentrates_on_arrayed_shared_bus_reasoning")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_sem22_failure_attribution(run_dirs=[root / "missing"], out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
