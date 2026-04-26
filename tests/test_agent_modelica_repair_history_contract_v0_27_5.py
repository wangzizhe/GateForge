from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_repair_history_contract_v0_27_5 import (
    build_repair_history_contract_summary,
    validate_repair_history_prompt,
)


class RepairHistoryContractV0275Tests(unittest.TestCase):
    def test_validate_requires_raw_feedback_transition(self) -> None:
        errors = validate_repair_history_prompt("Attempt 1\n- OMC result: checkModel FAILED.")
        self.assertIn("missing_input_omc_transition", errors)
        self.assertIn("missing_post_patch_omc_transition", errors)

    def test_validate_rejects_forbidden_hint_terms(self) -> None:
        errors = validate_repair_history_prompt(
            "OMC before this patch: raw\nOMC after this patch: raw\nrepair_hint: change R1"
        )
        self.assertIn("forbidden:repair_hint", errors)

    def test_build_summary_writes_contract_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = build_repair_history_contract_summary(out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["contains_input_omc_summary"])
            self.assertTrue(summary["contains_post_patch_omc_summary"])
            self.assertFalse(summary["discipline"]["deterministic_repair_added"])
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "canonical_history.json").exists())
            self.assertTrue((out_dir / "formatted_history.txt").exists())


if __name__ == "__main__":
    unittest.main()
