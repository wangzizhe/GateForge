from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gateforge.agent_modelica_difficulty_calibration_v0_38_0 import classify_seed_difficulty
from scripts.build_difficulty_calibration_from_baseline_v0_38_3 import load_run_evidence


class DifficultyCalibrationFromBaselineV0383Tests(unittest.TestCase):
    def test_single_fail_becomes_hard_candidate_not_hard_negative(self) -> None:
        row = classify_seed_difficulty(
            {
                "case_id": "case",
                "family": "family",
                "known_hard_for": [],
                "registry_status": "admitted",
                "admission_status": "admitted_via_live_failure",
                "repeatability_status": "repeatability_pending",
            },
            gate_row={"case_id": "case", "formal_benchmark_eligible": False, "blockers": [], "status": "PASS"},
            pass_count=0,
            fail_count=1,
        )
        self.assertEqual(row["difficulty_bucket"], "hard_candidate")

    def test_load_run_evidence_merges_multiple_result_files(self) -> None:
        with TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.jsonl"
            second = Path(tmp) / "second.jsonl"
            first.write_text(
                '{"case_id":"case_a","final_verdict":"FAIL"}\n'
                '{"case_id":"case_b","final_verdict":"PASS"}\n',
                encoding="utf-8",
            )
            second.write_text(
                '{"case_id":"case_a","final_verdict":"FAIL"}\n'
                '{"case_id":"case_b","final_verdict":"FAIL","provider_error":"service_unavailable"}\n',
                encoding="utf-8",
            )

            evidence = load_run_evidence([first, second])

        self.assertEqual(evidence["case_a"], {"pass_count": 0, "fail_count": 2})
        self.assertEqual(evidence["case_b"], {"pass_count": 1, "fail_count": 0})


if __name__ == "__main__":
    unittest.main()
