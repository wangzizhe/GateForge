from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_flow_repeatability_v0_34_17 import (
    build_connector_flow_repeatability,
)


def _write_run(root: Path, *, verdict: str, submitted: bool, success: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    result = 'resultFile = "/workspace/X.mat"' if success else 'Class X has 24 equation(s) and 24 variable(s). resultFile = ""'
    steps = [
        {
            "step": 1,
            "tool_calls": [{"name": "connector_flow_semantics_diagnostic"}],
            "tool_results": [{"name": "connector_flow_semantics_diagnostic", "result": "{}"}],
        },
        {
            "step": 2,
            "tool_calls": [{"name": "check_model"}],
            "tool_results": [{"name": "check_model", "result": result}],
        },
    ]
    if submitted:
        steps.append(
            {
                "step": 3,
                "tool_calls": [{"name": "submit_final"}],
                "tool_results": [{"name": "submit_final", "result": '{"status": "submitted"}'}],
            }
        )
    row = {
        "case_id": "case_a",
        "final_verdict": verdict,
        "submitted": submitted,
        "provider_error": "",
        "step_count": len(steps),
        "token_used": 10,
        "steps": steps,
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ConnectorFlowRepeatabilityV03417Tests(unittest.TestCase):
    def test_detects_positive_but_submit_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pass_run = root / "pass"
            missed_run = root / "missed"
            _write_run(pass_run, verdict="PASS", submitted=True, success=True)
            _write_run(missed_run, verdict="FAILED", submitted=False, success=True)
            summary = build_connector_flow_repeatability(
                run_dirs=[pass_run, missed_run],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["pass_count"], 1)
            self.assertEqual(summary["success_candidate_seen_count"], 2)
            self.assertEqual(summary["decision"], "connector_flow_semantics_positive_but_submit_unstable")

    def test_detects_balanced_without_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            _write_run(run, verdict="FAILED", submitted=False, success=False)
            summary = build_connector_flow_repeatability(run_dirs=[run], out_dir=root / "out")
            self.assertEqual(summary["balanced_without_success_count"], 1)
            self.assertEqual(summary["failure_class_counts"]["balanced_without_simulation_success"], 1)

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_connector_flow_repeatability(run_dirs=[root / "missing"], out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
