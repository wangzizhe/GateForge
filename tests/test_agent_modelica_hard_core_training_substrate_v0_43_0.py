from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gateforge.agent_modelica_hard_core_training_substrate_v0_43_0 import (
    build_training_substrate_summary,
    build_training_trajectory_records,
    hard_negative_case_ids,
)


class HardCoreTrainingSubstrateV0430Tests(unittest.TestCase):
    def test_hard_negative_case_ids_read_summary_list(self) -> None:
        self.assertEqual(
            hard_negative_case_ids({"formal_hard_negative_case_ids": ["b", "a"]}),
            ["a", "b"],
        )

    def test_records_exclude_provider_errors_and_passes(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            rows = [
                {"case_id": "hard", "final_verdict": "FAILED", "provider_error": "", "steps": []},
                {"case_id": "hard", "final_verdict": "PASS", "provider_error": "", "steps": []},
                {"case_id": "hard", "final_verdict": "FAILED", "provider_error": "timeout", "steps": []},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            records = build_training_trajectory_records(hard_case_ids=["hard"], result_paths=[path])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["case_id"], "hard")
        self.assertFalse(records[0]["contains_reference_solution"])
        self.assertFalse(records[0]["wrapper_repair_added"])

    def test_summary_requires_all_hard_cases_to_have_records(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text(
                json.dumps({"case_id": "hard_a", "final_verdict": "FAILED", "provider_error": "", "steps": []})
                + "\n",
                encoding="utf-8",
            )
            summary, records = build_training_substrate_summary(
                calibration_summary={"formal_hard_negative_case_ids": ["hard_a", "hard_b"]},
                result_paths=[path],
            )
        self.assertEqual(len(records), 1)
        self.assertEqual(summary["status"], "REVIEW")
        self.assertEqual(summary["missing_case_ids"], ["hard_b"])


if __name__ == "__main__":
    unittest.main()
