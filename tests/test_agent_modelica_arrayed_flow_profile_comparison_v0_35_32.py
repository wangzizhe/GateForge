from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_arrayed_flow_profile_comparison_v0_35_32 import (
    build_arrayed_flow_profile_comparison,
)


class ArrayedFlowProfileComparisonV03532Tests(unittest.TestCase):
    def test_detects_candidate_preference_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            candidate = root / "candidate"
            base.mkdir()
            candidate.mkdir()
            (base / "results.jsonl").write_text(
                json.dumps({"case_id": "a", "final_verdict": "PASS"}) + "\n"
                + json.dumps({"case_id": "b", "final_verdict": "PASS"}) + "\n",
                encoding="utf-8",
            )
            (candidate / "results.jsonl").write_text(
                json.dumps({"case_id": "a", "final_verdict": "PASS"}) + "\n"
                + json.dumps({"case_id": "b", "final_verdict": "FAILED"}) + "\n",
                encoding="utf-8",
            )
            summary = build_arrayed_flow_profile_comparison(base_dir=base, candidate_dir=candidate, out_dir=root / "out")
            self.assertEqual(summary["decision"], "candidate_preference_family_regresses")
            self.assertEqual(summary["regressed_case_ids"], ["b"])

    def test_missing_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_arrayed_flow_profile_comparison(
                base_dir=root / "missing_base",
                candidate_dir=root / "missing_candidate",
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
