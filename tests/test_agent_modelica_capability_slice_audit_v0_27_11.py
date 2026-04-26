from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_capability_slice_audit_v0_27_11 import (
    audit_capability_slice,
    run_capability_slice_audit,
)


def _plan(case_id: str) -> dict:
    return {
        "candidate_id": case_id,
        "family": "family",
        "slice_role": "capability_baseline",
        "repeatability_class": "stable_true_multi",
    }


def _failed_result(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "final_verdict": "FAILED",
        "repair_round_count": 3,
        "true_multi_turn": False,
        "attempts": [
            {"llm_called": True, "patched_text_present": True, "model_changed": True, "check_pass_after_patch": False, "raw_omc_after_patch": "Error: Wrong number of subscripts"},
            {"llm_called": True, "patched_text_present": True, "model_changed": True, "check_pass_after_patch": False, "raw_omc_after_patch": "Error: Too few equations, under-determined system."},
            {"llm_called": True, "patched_text_present": True, "model_changed": False, "check_pass_after_patch": False, "raw_omc_after_patch": "Error: Too few equations, under-determined system."},
        ],
    }


class CapabilitySliceAuditV02711Tests(unittest.TestCase):
    def test_audit_demotes_current_harness_baseline_when_all_cases_stall(self) -> None:
        cases, summary = audit_capability_slice(
            slice_plan_rows=[_plan("c1"), _plan("c2")],
            result_rows=[_failed_result("c1"), _failed_result("c2")],
        )
        self.assertEqual(summary["decision"], "demote_capability_baseline_for_current_deepseek_harness")
        self.assertEqual(summary["pass_count"], 0)
        self.assertEqual(summary["failure_signal_count"], 2)
        self.assertTrue(all(row["current_harness_baseline_failure_signal"] for row in cases))

    def test_audit_does_not_demote_when_case_passes(self) -> None:
        passed = _failed_result("c1")
        passed["final_verdict"] = "PASS"
        passed["attempts"][-1]["check_pass_after_patch"] = True
        passed["attempts"][-1]["raw_omc_after_patch"] = "Check completed successfully."
        cases, summary = audit_capability_slice(slice_plan_rows=[_plan("c1")], result_rows=[passed])
        self.assertEqual(summary["decision"], "capability_baseline_status_needs_more_evidence")
        self.assertFalse(cases[0]["current_harness_baseline_failure_signal"])

    def test_run_audit_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.jsonl"
            results = root / "results.jsonl"
            plan.write_text(json.dumps(_plan("c1")) + "\n", encoding="utf-8")
            results.write_text(json.dumps(_failed_result("c1")) + "\n", encoding="utf-8")
            summary = run_capability_slice_audit(
                slice_plan_path=plan,
                results_path=results,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "case_audits.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
