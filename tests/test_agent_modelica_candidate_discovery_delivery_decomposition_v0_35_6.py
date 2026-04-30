from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_discovery_delivery_decomposition_v0_35_6 import (
    build_candidate_discovery_delivery_decomposition,
)


def _write_run(path: Path, *, case_id: str, success: bool, submitted: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    result = 'resultFile = "/workspace/X.mat"' if success else "check failed"
    row = {
        "case_id": case_id,
        "final_verdict": "PASS" if submitted else "FAILED",
        "submitted": submitted,
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


class CandidateDiscoveryDeliveryDecompositionV0356Tests(unittest.TestCase):
    def test_detects_discovery_primary_bottleneck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failed = root / "failed"
            missed = root / "missed"
            _write_run(failed, case_id="case_a", success=False, submitted=False)
            _write_run(missed, case_id="case_b", success=True, submitted=False)
            summary = build_candidate_discovery_delivery_decomposition(
                run_dirs={"failed": failed, "missed": missed},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["discovery_failure_count"], 1)
            self.assertEqual(summary["missed_success_count"], 1)
            self.assertEqual(summary["decision"], "delivery_discipline_is_primary_bottleneck")

    def test_missing_profile_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_candidate_discovery_delivery_decomposition(
                run_dirs={"missing": root / "missing"},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
