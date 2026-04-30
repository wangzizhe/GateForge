from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_flow_family_profile_comparison_v0_35_3 import (
    build_connector_flow_family_profile_comparison,
)


def _write_run(path: Path, *, success: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    result = 'resultFile = "/workspace/X.mat"' if success else "check failed"
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
                "tool_calls": [{"name": "check_model"}],
                "tool_results": [{"name": "check_model", "result": result}],
            }
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ConnectorFlowFamilyProfileComparisonV0353Tests(unittest.TestCase):
    def test_detects_delivery_gap_without_pass_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            semantic = root / "semantic"
            _write_run(base, success=True)
            _write_run(semantic, success=False)
            summary = build_connector_flow_family_profile_comparison(
                profile_run_dirs={"base": base, "semantic": semantic},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["best_success_candidate_seen_count"], 1)
            self.assertEqual(summary["decision"], "connector_flow_profiles_expose_delivery_gap_without_pass_gain")

    def test_missing_profile_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_connector_flow_family_profile_comparison(
                profile_run_dirs={"missing": root / "missing"},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
