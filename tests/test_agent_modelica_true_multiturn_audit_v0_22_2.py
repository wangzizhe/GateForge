from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_true_multiturn_audit_v0_22_2 import (
    audit_run_dir,
    classify_quality,
    run_true_multiturn_audit,
    summarize_audit,
)


def _new_executor_payload(status: str, repairs: int, attempts: int) -> dict:
    rows = []
    for index in range(attempts):
        row = {"observed_failure_type": "model_check_error" if index + 1 < attempts else "none"}
        if index < repairs:
            row["declaration_fix_repair"] = {"applied": True, "err": "", "provider": "gemini"}
        rows.append(row)
    return {"executor_status": status, "attempts": rows, "task_id": "new_case"}


def _legacy_payload(status: str, repairs: int) -> dict:
    return {
        "final_status": status,
        "candidate_id": "legacy_case",
        "attempts": [
            {
                "observed_state_before_patch": "model_check_error",
                "patched_text_present": True,
                "model_changed": True,
            }
            for _ in range(repairs)
        ],
    }


class TrueMultiturnAuditV0222Tests(unittest.TestCase):
    def test_classify_quality_does_not_count_validation_round_as_multiturn(self) -> None:
        payload = _new_executor_payload("PASS", repairs=1, attempts=2)

        self.assertEqual(classify_quality(payload), "single_repair_then_validate")

    def test_classify_quality_requires_two_repairs_for_true_multiturn(self) -> None:
        payload = _new_executor_payload("PASS", repairs=2, attempts=3)

        self.assertEqual(classify_quality(payload), "true_multi_repair_pass")

    def test_legacy_attempts_count_as_repair_rounds_when_patch_applied(self) -> None:
        payload = _legacy_payload("PASS", repairs=2)

        self.assertEqual(classify_quality(payload), "true_multi_repair_pass")

    def test_audit_run_dir_reads_raw_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            (raw_dir / "case.json").write_text(json.dumps(_new_executor_payload("PASS", 1, 2)), encoding="utf-8")

            rows = audit_run_dir(root)

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["false_multiturn_by_attempt_count"])
        self.assertEqual(rows[0]["repair_round_count"], 1)

    def test_run_true_multiturn_audit_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            raw_dir = run_dir / "raw"
            out_dir = root / "out"
            raw_dir.mkdir(parents=True)
            (raw_dir / "a.json").write_text(json.dumps(_new_executor_payload("PASS", 1, 2)), encoding="utf-8")
            (raw_dir / "b.json").write_text(json.dumps(_new_executor_payload("PASS", 2, 3)), encoding="utf-8")

            summary = run_true_multiturn_audit(run_dirs=[run_dir], out_dir=out_dir)

            self.assertEqual(summary["audited_case_count"], 2)
            self.assertEqual(summary["true_multi_repair_pass_count"], 1)
            self.assertEqual(summary["false_multiturn_by_attempt_count"], 1)
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "case_audit.jsonl").exists())

    def test_summarize_audit_counts_quality(self) -> None:
        summary = summarize_audit(
            [
                {"status": "PASS", "sample_quality": "single_repair_then_validate", "false_multiturn_by_attempt_count": True, "run_dir": "a"},
                {"status": "PASS", "sample_quality": "true_multi_repair_pass", "false_multiturn_by_attempt_count": False, "run_dir": "a"},
            ]
        )

        self.assertEqual(summary["quality_counts"]["true_multi_repair_pass"], 1)
        self.assertEqual(summary["false_multiturn_by_attempt_count"], 1)


if __name__ == "__main__":
    unittest.main()
