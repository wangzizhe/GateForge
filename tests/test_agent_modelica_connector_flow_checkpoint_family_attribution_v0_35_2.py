from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_flow_checkpoint_family_attribution_v0_35_2 import (
    build_connector_flow_checkpoint_family_attribution,
)


class ConnectorFlowCheckpointFamilyAttributionV0352Tests(unittest.TestCase):
    def test_detects_candidate_discovery_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            row = {
                "case_id": "case_a",
                "final_verdict": "FAILED",
                "submitted": False,
                "provider_error": "",
                "step_count": 1,
                "token_used": 5,
                "steps": [
                    {
                        "step": 1,
                        "tool_calls": [{"name": "connector_flow_semantics_diagnostic"}],
                        "tool_results": [{"name": "connector_flow_semantics_diagnostic", "result": "{}"}],
                    }
                ],
            }
            (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
            summary = build_connector_flow_checkpoint_family_attribution(run_dir=run_dir, out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["success_candidate_seen_count"], 0)
            self.assertEqual(summary["decision"], "connector_flow_checkpoint_family_exposes_candidate_discovery_gap")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_connector_flow_checkpoint_family_attribution(run_dir=root / "missing", out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
