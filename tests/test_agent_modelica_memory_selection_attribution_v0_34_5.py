from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_memory_selection_attribution_v0_34_5 import build_memory_selection_attribution


def _write_run(root: Path, *, verdict: str = "FAILED") -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": "case_a",
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "provider_error": "",
        "token_used": 10,
        "step_count": 2,
        "steps": [
            {
                "step": 1,
                "tool_calls": [
                    {
                        "name": "record_semantic_memory_selection",
                        "arguments": {
                            "selected_unit_ids": ["standard_library_semantic_substitution"],
                            "rejected_unit_ids": [],
                            "rationale": "x",
                            "risk": "y",
                        },
                    }
                ],
            }
        ],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class MemorySelectionAttributionV0345Tests(unittest.TestCase):
    def test_records_visible_selection_without_capability_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "a"
            run_b = root / "b"
            _write_run(run_a)
            _write_run(run_b)
            summary = build_memory_selection_attribution(run_dirs=[run_a, run_b], out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["selection_call_count"], 2)
            self.assertEqual(summary["pass_count"], 0)
            self.assertEqual(summary["decision"], "memory_selection_visible_but_not_capability_improving")
            self.assertFalse(summary["discipline"]["wrapper_memory_selection_added"])

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_memory_selection_attribution(run_dirs=[root / "missing"], out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
