from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_flow_state_repeatability_v0_35_11 import (
    build_connector_flow_state_repeatability,
)


def _write_run(path: Path, *, case_id: str, verdict: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": case_id,
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "provider_error": "",
        "step_count": 1,
        "token_used": 5,
        "steps": [
            {
                "step": 1,
                "tool_calls": [{"name": "connector_flow_state_diagnostic"}],
                "tool_results": [{"name": "connector_flow_state_diagnostic", "result": "{}"}],
            }
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ConnectorFlowStateRepeatabilityV03511Tests(unittest.TestCase):
    def test_detects_positive_but_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "run_a"
            run_b = root / "run_b"
            _write_run(run_a, case_id="case_a", verdict="PASS")
            _write_run(run_b, case_id="case_b", verdict="FAILED")
            summary = build_connector_flow_state_repeatability(run_dirs=[run_a, run_b], out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["pass_counts"], [1, 0])
            self.assertEqual(summary["decision"], "connector_flow_state_positive_but_unstable")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_connector_flow_state_repeatability(run_dirs=[root / "missing"], out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
