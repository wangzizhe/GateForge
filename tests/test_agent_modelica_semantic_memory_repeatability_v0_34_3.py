from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_semantic_memory_repeatability_v0_34_3 import build_semantic_memory_repeatability


def _write_run(root: Path, *, verdict: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": "target",
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "provider_error": "",
        "token_used": 10,
        "step_count": 1,
        "steps": [{"tool_calls": [{"name": "check_model"}]}],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class SemanticMemoryRepeatabilityV0343Tests(unittest.TestCase):
    def test_marks_partial_repeatability_as_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "a"
            run_b = root / "b"
            _write_run(run_a, verdict="PASS")
            _write_run(run_b, verdict="FAILED")
            summary = build_semantic_memory_repeatability(
                run_specs=[
                    {"run_id": "a", "path": run_a, "case_id": "target"},
                    {"run_id": "b", "path": run_b, "case_id": "target"},
                ],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["pass_count"], 1)
            self.assertEqual(summary["decision"], "semantic_memory_units_positive_but_unstable")

    def test_missing_case_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_semantic_memory_repeatability(
                run_specs=[{"run_id": "missing", "path": root / "missing", "case_id": "target"}],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
