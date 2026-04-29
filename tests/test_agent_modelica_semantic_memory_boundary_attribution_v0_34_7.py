from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_semantic_memory_boundary_attribution_v0_34_7 import (
    build_semantic_memory_boundary_attribution,
)


def _write_run(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": "case_a",
        "final_verdict": "FAILED",
        "submitted": False,
        "provider_error": "",
        "steps": [
            {
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}],
                "tool_results": [{"name": "check_model", "result": 'resultFile = "/workspace/X.mat"'}],
            },
            {
                "tool_calls": [
                    {
                        "name": "candidate_acceptance_critique",
                        "arguments": {
                            "omc_passed": True,
                            "concern": "This may not repair the reusable contract.",
                            "task_constraints": ["repair reusable contract"],
                        },
                    }
                ],
                "tool_results": [],
            },
        ],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class SemanticMemoryBoundaryAttributionV0347Tests(unittest.TestCase):
    def test_detects_oracle_boundary_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            _write_run(run)
            summary = build_semantic_memory_boundary_attribution(
                run_dirs={"run": run},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "semantic_memory_exposes_oracle_boundary_gap")
            self.assertFalse(summary["discipline"]["oracle_extended"])

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_semantic_memory_boundary_attribution(
                run_dirs={"missing": root / "missing"},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
