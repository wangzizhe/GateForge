from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_family_hard_negative_audit_v0_27_7 import (
    audit_family_hard_negative,
    run_family_hard_negative_audit,
)


def _candidate(case_id: str) -> dict:
    return {
        "candidate_id": case_id,
        "mutation_pattern": "single_point_resistor_observability_refactor",
        "source_complexity_class": "small",
        "source_viability_status": "historically_verified_clean_source",
        "residual_count": 3,
        "residual_chain": ["scalar to indexed access", "missing probe", "observability residual"],
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


class FamilyHardNegativeAuditV0277Tests(unittest.TestCase):
    def test_audit_marks_all_failed_stalled_cases_as_hard_negative(self) -> None:
        cases, summary = audit_family_hard_negative(
            candidate_rows=[_candidate("c1"), _candidate("c2")],
            result_rows=[_failed_result("c1"), _failed_result("c2")],
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["decision"], "treat_family_as_current_hard_negative")
        self.assertEqual(summary["hard_negative_signal_count"], 2)
        self.assertEqual(summary["final_round_stall_count"], 2)
        self.assertTrue(all(row["hard_negative_signal"] for row in cases))
        self.assertFalse(summary["discipline"]["deterministic_repair_added"])

    def test_audit_does_not_claim_hard_negative_when_case_passes(self) -> None:
        passing = _failed_result("c1")
        passing["final_verdict"] = "PASS"
        passing["attempts"][-1]["check_pass_after_patch"] = True
        passing["attempts"][-1]["raw_omc_after_patch"] = "Check completed successfully."
        cases, summary = audit_family_hard_negative(candidate_rows=[_candidate("c1")], result_rows=[passing])
        self.assertEqual(summary["decision"], "family_hard_negative_status_needs_more_evidence")
        self.assertFalse(cases[0]["hard_negative_signal"])

    def test_run_audit_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.jsonl"
            results = root / "results.jsonl"
            candidates.write_text(json.dumps(_candidate("c1")) + "\n", encoding="utf-8")
            results.write_text(json.dumps(_failed_result("c1")) + "\n", encoding="utf-8")
            summary = run_family_hard_negative_audit(
                candidates_path=candidates,
                results_path=results,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "case_audits.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
