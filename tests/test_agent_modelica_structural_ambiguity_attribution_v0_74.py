from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_structural_ambiguity_attribution_v0_74_0 import (
    build_structural_ambiguity_attribution,
    classify_candidate_strategy,
)


class StructuralAmbiguityAttributionV074Tests(unittest.TestCase):
    def test_classify_candidate_strategy_uses_candidate_metadata(self) -> None:
        self.assertEqual(classify_candidate_strategy({"candidate_id": "initial"}), "initial_check")
        self.assertEqual(
            classify_candidate_strategy({"candidate_id": "c1", "rationale": "Add nullspace projection"}),
            "nullspace_or_projection_closure",
        )
        self.assertEqual(
            classify_candidate_strategy({"candidate_id": "c2", "rationale": "Remove redundant equation"}),
            "remove_redundant_constraint",
        )

    def test_build_structural_ambiguity_attribution_detects_budget_sensitive_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            low = root / "low.jsonl"
            high = root / "high.jsonl"
            low.write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "final_verdict": "FAILED",
                        "candidate_files": [
                            {"candidate_id": "initial"},
                            {"candidate_id": "c1", "rationale": "Remove redundant equation", "write_check_ok": True},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            high.write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "final_verdict": "PASS",
                        "submitted": True,
                        "candidate_files": [
                            {"candidate_id": "initial"},
                            {
                                "candidate_id": "c2",
                                "rationale": "Add nullspace projection",
                                "write_check_ok": True,
                                "write_simulate_ok": True,
                            },
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            summary = build_structural_ambiguity_attribution(
                result_paths_by_budget={"32k": low, "96k": high},
                out_dir=root / "out",
            )
            self.assertEqual(summary["budget_sensitive_case_ids"], ["case_a"])
            self.assertTrue((root / "out" / "case_patterns.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
