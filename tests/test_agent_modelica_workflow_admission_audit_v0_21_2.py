from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_workflow_admission_audit_v0_21_2 import (
    audit_family_candidate,
    run_workflow_admission_audit,
    summarize_audit,
)


def _family_candidate(
    *,
    source_status: str = "pending_clean_source_pairing",
    target_status: str = "pending_omc_validation",
) -> dict:
    return {
        "family_candidate_id": "v0211_a",
        "source_task_id": "task_a",
        "bucket_id": "ET01",
        "family_id": "generation_parse_load_failure",
        "mutation_goal": "represent parser failures",
        "real_failure_linked": True,
        "workflow_proximal_evidence": True,
        "source_viability_status": source_status,
        "target_failure_status": target_status,
        "benchmark_admission_status": "isolated_family_candidate_only",
    }


class WorkflowAdmissionAuditV0212Tests(unittest.TestCase):
    def test_audit_family_candidate_blocks_pending_source_and_target_validation(self) -> None:
        row = audit_family_candidate(_family_candidate())

        self.assertEqual(row["main_benchmark_status"], "blocked_from_main_benchmark")
        self.assertIn("source_viability_verified", row["blocking_reasons"])
        self.assertIn("target_failure_verified", row["blocking_reasons"])

    def test_audit_family_candidate_allows_main_when_all_gates_verified(self) -> None:
        row = audit_family_candidate(
            _family_candidate(
                source_status="verified_clean_source",
                target_status="verified_target_failure",
            )
        )

        self.assertEqual(row["main_benchmark_status"], "main_admissible")
        self.assertEqual(row["blocking_reasons"], [])

    def test_summarize_audit_reports_do_not_promote_when_all_blocked(self) -> None:
        rows = [audit_family_candidate(_family_candidate()), audit_family_candidate(_family_candidate())]

        summary = summarize_audit(rows)

        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["main_admissible_count"], 0)
        self.assertEqual(summary["blocked_from_main_benchmark_count"], 2)
        self.assertEqual(summary["benchmark_admission_decision"], "do_not_promote_to_main_benchmark")

    def test_run_workflow_admission_audit_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_path = root / "family_candidates.jsonl"
            out_dir = root / "out"
            candidate_path.write_text(json.dumps(_family_candidate()), encoding="utf-8")

            summary = run_workflow_admission_audit(
                family_candidate_path=candidate_path,
                out_dir=out_dir,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "audited_candidates.jsonl").exists())
            self.assertTrue((out_dir / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
