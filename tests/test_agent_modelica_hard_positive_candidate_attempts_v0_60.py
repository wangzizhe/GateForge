from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_hard_positive_candidate_attempts_v0_60_1 import (
    build_hard_positive_candidate_attempts,
    run_hard_positive_candidate_attempts,
)


class HardPositiveCandidateAttemptsV060Tests(unittest.TestCase):
    def test_attempt_summary_records_failed_hidden_attempts(self) -> None:
        summary, rows = build_hard_positive_candidate_attempts(
            workbench_summary={"case_ids": ["case_a"]},
            attempts=(
                {
                    "case_id": "case_a",
                    "attempt_id": "simple",
                    "attempt_family": "probe",
                    "verification_status": "FAIL",
                    "observed_result": "not_verified",
                },
            ),
        )
        self.assertEqual(summary["failed_attempt_count"], 1)
        self.assertEqual(summary["verified_pass_count"], 0)
        self.assertTrue(summary["scope_contract"]["failed_attempts_do_not_enter_prompt"])
        self.assertEqual(rows[0]["attempt_id"], "simple")

    def test_run_attempts_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbench = root / "workbench.json"
            workbench.write_text('{"case_ids":["sem_29_two_branch_probe_bus"]}', encoding="utf-8")
            out = root / "out"
            summary = run_hard_positive_candidate_attempts(workbench_path=workbench, out_dir=out)
            self.assertEqual(summary["attempt_count"], 1)
            self.assertTrue((out / "attempts.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
