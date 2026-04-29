from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_semantic_memory_live_comparison_v0_34_2 import (
    build_semantic_memory_live_comparison,
)


def _write_run(root: Path, rows: list[dict]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with (root / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            payload = {
                "case_id": row["case_id"],
                "final_verdict": row["verdict"],
                "submitted": row["verdict"] == "PASS",
                "provider_error": row.get("provider_error", ""),
                "token_used": 10,
                "step_count": 1,
                "steps": [{"tool_calls": [{"name": "check_model"}]}],
            }
            fh.write(json.dumps(payload) + "\n")


class SemanticMemoryLiveComparisonV0342Tests(unittest.TestCase):
    def test_detects_partial_positive_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            memory = root / "memory"
            _write_run(baseline, [{"case_id": "a", "verdict": "FAILED"}, {"case_id": "b", "verdict": "FAILED"}])
            _write_run(memory, [{"case_id": "a", "verdict": "PASS"}, {"case_id": "b", "verdict": "FAILED"}])
            summary = build_semantic_memory_live_comparison(
                baseline_dir=baseline,
                memory_dir=memory,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["improved_count"], 1)
            self.assertEqual(summary["decision"], "semantic_memory_units_show_partial_positive_live_signal")
            self.assertFalse(summary["discipline"]["wrapper_patch_generated"])

    def test_provider_error_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            memory = root / "memory"
            _write_run(baseline, [{"case_id": "a", "verdict": "FAILED"}])
            _write_run(memory, [{"case_id": "a", "verdict": "FAILED", "provider_error": "timeout"}])
            summary = build_semantic_memory_live_comparison(
                baseline_dir=baseline,
                memory_dir=memory,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
