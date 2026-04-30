from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_flow_state_ab_v0_35_10 import build_connector_flow_state_ab


def _write_run(path: Path, *, verdict: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": "case_a",
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "provider_error": "",
        "step_count": 1,
        "token_used": 5,
        "steps": [
            {
                "step": 1,
                "tool_calls": [{"name": "submit_final"}] if verdict == "PASS" else [{"name": "check_model"}],
                "tool_results": [{"name": "check_model", "result": "check failed"}],
            }
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ConnectorFlowStateABV03510Tests(unittest.TestCase):
    def test_detects_matching_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            state = root / "state"
            _write_run(base, verdict="PASS")
            _write_run(state, verdict="PASS")
            summary = build_connector_flow_state_ab(
                run_dirs={"base_submit_checkpoint_run_01": base, "connector_flow_state_checkpoint": state},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "connector_flow_state_matches_checkpoint_baseline")

    def test_missing_profile_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_connector_flow_state_ab(
                run_dirs={"connector_flow_state_checkpoint": root / "missing"},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
