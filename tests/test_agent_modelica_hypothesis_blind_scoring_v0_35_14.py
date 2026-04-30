from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_hypothesis_blind_scoring_v0_35_14 import build_hypothesis_blind_scoring


class HypothesisBlindScoringV03514Tests(unittest.TestCase):
    def test_scores_semantic_hit_with_overconstraint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": "sem_23_nested_probe_contract_bus",
                "final_verdict": "FAILED",
                "steps": [
                    {
                        "tool_calls": [
                            {
                                "name": "record_repair_hypothesis",
                                "arguments": {
                                    "semantic_type": "connector_flow_ownership",
                                    "target_boundary": "ProbeBank local implementation",
                                    "candidate_strategy": "set all pin currents to zero",
                                    "expected_equation_delta": 4,
                                    "fallback_hypothesis": "try paired flow",
                                },
                            }
                        ]
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_hypothesis_blind_scoring(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["semantic_hit_cases"], 1)
            self.assertEqual(summary["over_constraint_risk_cases"], 1)

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_hypothesis_blind_scoring(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
