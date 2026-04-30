from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_flow_family_live_attribution_v0_35_1 import (
    build_connector_flow_family_live_attribution,
)


def _write_results(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "case_id": "case_a",
            "final_verdict": "FAILED",
            "submitted": False,
            "provider_error": "",
            "step_count": 2,
            "token_used": 10,
            "steps": [
                {
                    "step": 1,
                    "tool_calls": [{"name": "connector_flow_semantics_diagnostic"}],
                    "tool_results": [{"name": "connector_flow_semantics_diagnostic", "result": "{}"}],
                },
                {
                    "step": 2,
                    "tool_calls": [{"name": "check_model"}],
                    "tool_results": [{"name": "check_model", "result": 'resultFile = "/workspace/X.mat"'}],
                },
            ],
        },
        {
            "case_id": "case_b",
            "final_verdict": "FAILED",
            "submitted": False,
            "provider_error": "",
            "step_count": 1,
            "token_used": 5,
            "steps": [
                {
                    "step": 1,
                    "tool_calls": [{"name": "check_model"}],
                    "tool_results": [{"name": "check_model", "result": "Class X has 24 equation(s) and 24 variable(s)."}],
                }
            ],
        },
    ]
    (path / "results.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class ConnectorFlowFamilyLiveAttributionV0351Tests(unittest.TestCase):
    def test_detects_submit_discipline_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_results(run_dir)
            summary = build_connector_flow_family_live_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["success_candidate_seen_count"], 1)
            self.assertEqual(summary["outcome_class_counts"]["success_candidate_seen_without_submit"], 1)
            self.assertEqual(summary["decision"], "connector_flow_family_exposes_submit_discipline_gap")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_connector_flow_family_live_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
