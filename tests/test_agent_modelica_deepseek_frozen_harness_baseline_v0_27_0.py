from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_deepseek_frozen_harness_baseline_v0_27_0 import (
    run_deepseek_frozen_harness_baseline,
    run_live_case,
)


class DeepSeekFrozenHarnessBaselineV0270Tests(unittest.TestCase):
    def test_run_live_case_uses_observation_contract_and_raw_only(self) -> None:
        checks = iter(
            [
                (False, "model_check_error"),
                (True, "none"),
            ]
        )

        def check_fn(_text: str, _model_name: str):
            return next(checks)

        def repair_fn(**_kwargs):
            return "model Demo\n  Real x;\nequation\n  x = 0;\nend Demo;\n", "", "deepseek"

        result = run_live_case(
            {
                "case_id": "c1",
                "model_name": "Demo",
                "failure_type": "model_check_error",
                "workflow_goal": "Repair.",
                "model_text": "model Demo\n  Real x;\nend Demo;\n",
            },
            max_rounds=2,
            check_fn=check_fn,
            repair_fn=repair_fn,
        )
        self.assertEqual(result["final_verdict"], "PASS")
        self.assertEqual(result["provider"], "deepseek")
        self.assertEqual(result["run_mode"], "raw_only")
        self.assertEqual(result["observation_validation_error_count"], 0)
        self.assertEqual(result["repair_round_count"], 1)
        self.assertFalse(result["true_multi_turn"])

    def test_run_baseline_writes_outputs(self) -> None:
        def check_fn(text: str, _model_name: str):
            return ("equation" in text), "none" if "equation" in text else "model_check_error"

        def repair_fn(**_kwargs):
            return "model Demo\n  Real x;\nequation\n  x = 0;\nend Demo;\n", "", "deepseek"

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = run_deepseek_frozen_harness_baseline(
                out_dir=out_dir,
                cases=[
                    {
                        "case_id": "c1",
                        "model_name": "Demo",
                        "failure_type": "model_check_error",
                        "workflow_goal": "Repair.",
                        "model_text": "model Demo\n  Real x;\nend Demo;\n",
                    }
                ],
                limit=1,
                max_rounds=2,
                check_fn=check_fn,
                repair_fn=repair_fn,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["case_count"], 1)
            self.assertEqual(summary["pass_count"], 1)
            self.assertFalse(summary["discipline"]["comparative_claim_made"])
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "results.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
