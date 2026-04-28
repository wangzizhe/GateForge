from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_structure_coverage_probe_summary_v0_31_2 import (
    build_structure_coverage_probe_summary,
)


def _write(path: Path, *, coverage: bool, verdict: str = "FAILED") -> None:
    path.mkdir(parents=True, exist_ok=True)
    calls = [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}]
    if coverage:
        calls.append({"name": "structure_coverage_diagnostic", "arguments": {"candidates": []}})
    row = {
        "case_id": "sem_case",
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "token_used": 1000,
        "steps": [{"step": 1, "tool_calls": calls, "tool_results": [{"name": "check_model", "result": "Failed"}]}],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class StructureCoverageProbeSummaryV0312Tests(unittest.TestCase):
    def test_summary_reports_invoked_without_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write(run_dir, coverage=True)
            summary = build_structure_coverage_probe_summary(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["coverage_call_count"], 1)
            self.assertEqual(summary["decision"], "structure_coverage_invoked_without_discovery_gain")


if __name__ == "__main__":
    unittest.main()
