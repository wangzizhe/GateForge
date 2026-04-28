from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_critique_trigger_audit_v0_30_2 import (
    build_candidate_critique_trigger_audit,
)


def _write_row(
    path: Path,
    *,
    case_id: str,
    submitted: bool,
    critique: bool,
    successful_tool: bool,
) -> None:
    path.mkdir(parents=True)
    calls = [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}]
    if critique:
        calls.append({"name": "candidate_acceptance_critique", "arguments": {"omc_passed": True}})
    result = 'resultFile = "/workspace/X_res.mat"' if successful_tool else "Failed to build model"
    row = {
        "case_id": case_id,
        "final_verdict": "PASS" if submitted else "FAILED",
        "submitted": submitted,
        "token_used": 1000,
        "steps": [
            {
                "step": 1,
                "tool_calls": calls,
                "tool_results": [{"name": "check_model", "result": result}],
            },
            {
                "step": 2,
                "tool_calls": [{"name": "simulate_model", "arguments": {"model_text": "model X end X;"}}],
                "tool_results": [],
            },
        ],
    }
    (path / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class CandidateCritiqueTriggerAuditV0302Tests(unittest.TestCase):
    def test_audit_reports_checkpoint_need_for_missed_success_without_critique(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            _write_row(run_dir, case_id="sem_case", submitted=False, critique=False, successful_tool=True)
            summary = build_candidate_critique_trigger_audit(
                run_dirs={"probe": run_dir},
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "transparent_checkpoint_needed")
            self.assertEqual(summary["trigger_opportunity_count"], 1)
            self.assertEqual(summary["trigger_opportunities"][0]["post_success_tool_names"], ["simulate_model"])
            self.assertTrue((root / "out" / "summary.json").exists())

    def test_audit_does_not_count_submitted_or_critiqued_rows_as_trigger_opportunities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            submitted = root / "submitted"
            critiqued = root / "critiqued"
            _write_row(submitted, case_id="submitted_case", submitted=True, critique=False, successful_tool=True)
            _write_row(critiqued, case_id="critiqued_case", submitted=False, critique=True, successful_tool=True)
            summary = build_candidate_critique_trigger_audit(
                run_dirs={"submitted": submitted, "critiqued": critiqued},
                out_dir=root / "out",
            )
            self.assertEqual(summary["trigger_opportunity_count"], 0)
            self.assertEqual(summary["decision"], "candidate_critique_trigger_sufficient")


if __name__ == "__main__":
    unittest.main()
