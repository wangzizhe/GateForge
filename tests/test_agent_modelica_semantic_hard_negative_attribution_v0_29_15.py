from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_semantic_hard_negative_attribution_v0_29_15 import (
    build_semantic_hard_negative_attribution,
)


def _write_result(path: Path, case_id: str) -> None:
    path.mkdir(parents=True)
    row = {
        "case_id": case_id,
        "final_verdict": "FAILED",
        "submitted": False,
        "token_used": 34000,
        "step_count": 2,
        "steps": [
            {"text": "replaceable constrainedby partial flow equation underdetermined", "tool_calls": [{"name": "check_model"}]},
            {"text": "duplicate circular equation attempt", "tool_calls": [{"name": "get_unmatched_vars"}]},
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class SemanticHardNegativeAttributionV02915Tests(unittest.TestCase):
    def test_build_summary_identifies_semantic_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arm_dirs = {}
            for arm in ["base", "structural", "connector", "semantic"]:
                arm_dirs[arm] = root / arm
                _write_result(arm_dirs[arm], "sem_06")
            summary = build_semantic_hard_negative_attribution(
                arm_dirs=arm_dirs,
                case_ids=["sem_06"],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["semantic_gap_count"], 1)
            self.assertEqual(
                summary["decision"],
                "semantic_hard_negatives_indicate_replaceable_partial_flow_semantics_gap",
            )
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
