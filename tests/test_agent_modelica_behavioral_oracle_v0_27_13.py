from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_behavioral_oracle_v0_27_13 import (
    build_behavioral_oracle_summary,
    run_behavioral_oracle,
    validate_oracle_feedback,
)
from gateforge.agent_modelica_deepseek_frozen_harness_baseline_v0_27_0 import (
    BUILTIN_CASES,
    run_live_case,
)


class BehavioralOracleV02713Tests(unittest.TestCase):
    def test_check_and_simulate_pass_yields_behavior_pass(self) -> None:
        verdict, feedback = run_behavioral_oracle(
            check_ok=True, simulate_ok=True, raw_output="all good", model_name="Demo",
        )
        self.assertEqual(verdict, "behavior_pass")
        self.assertIn("behavioral_oracle_verdict: PASS", feedback)
        self.assertIn("checkModel: PASS", feedback)
        self.assertIn("simulate: PASS", feedback)

    def test_check_pass_simulate_fail_yields_behavior_error(self) -> None:
        raw = "Check of Demo completed successfully.\nClass Demo has 5 equation(s) and 6 variable(s).\nrecord SimulationResult\nresultFile = \"\"\nmessages = \"Failed to build model: Demo\"\nend SimulationResult;\n\"Error: Too few equations, under-determined system. The model has 5 equation(s) and 6 variable(s).\""
        verdict, feedback = run_behavioral_oracle(
            check_ok=True, simulate_ok=False, raw_output=raw, model_name="Demo",
        )
        self.assertEqual(verdict, "behavior_error")
        self.assertIn("behavioral_oracle_verdict: FAIL", feedback)
        self.assertIn("checkModel: PASS", feedback)
        self.assertIn("simulate: FAIL", feedback)
        self.assertIn("Too few equations", feedback)

    def test_check_fail_yields_infra_error(self) -> None:
        verdict, feedback = run_behavioral_oracle(
            check_ok=False, simulate_ok=False, raw_output="error", model_name="Demo",
        )
        self.assertEqual(verdict, "infra_error")
        self.assertIn("behavioral_oracle_verdict: N/A", feedback)
        self.assertIn("checkModel: FAIL", feedback)
        self.assertIn("requires checkModel pass", feedback)

    def test_simulation_error_extracts_underdetermined_detail(self) -> None:
        raw = "Check of Demo completed successfully.\nClass Demo has 5 equation(s) and 6 variable(s).\nrecord SimulationResult\nresultFile = \"\"\nend SimulationResult;\n\"Error: Too few equations, under-determined system.\"\n[/tmp/Demo.mo:9:3-9:25:writable] Warning: Variable R1ResidualCurrent does not have any remaining equation to be solved in.\n  The original equations were:\n  Equation 29: R1ResidualCurrent = R1.i + R1ResidualProbe, which needs to solve for R1ResidualProbe"
        verdict, feedback = run_behavioral_oracle(
            check_ok=True, simulate_ok=False, raw_output=raw, model_name="R1",
        )
        self.assertEqual(verdict, "behavior_error")
        self.assertIn("R1ResidualCurrent", feedback)
        self.assertIn("under-determined", feedback.lower())

    def test_feedback_includes_model_name(self) -> None:
        _, feedback = run_behavioral_oracle(
            check_ok=True, simulate_ok=True, raw_output="ok", model_name="SmallRC",
        )
        self.assertIn("model: SmallRC", feedback)

    def test_validate_accepts_clean_feedback(self) -> None:
        _, feedback = run_behavioral_oracle(
            check_ok=True, simulate_ok=True, raw_output="ok", model_name="X",
        )
        errors = validate_oracle_feedback(feedback)
        self.assertEqual(errors, [])

    def test_validate_rejects_hint_terms(self) -> None:
        errors = validate_oracle_feedback("You should fix the equation. repair_hint: add connect")
        self.assertIn("forbidden:you should", errors)
        self.assertIn("forbidden:repair_hint", errors)

    def test_validate_rejects_root_cause(self) -> None:
        errors = validate_oracle_feedback("root cause: missing equation")
        self.assertIn("forbidden:root cause", errors)

    def test_build_summary_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = build_behavioral_oracle_summary(out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertFalse(summary["discipline"]["hint_terms_found"])
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "canonical_results.jsonl").exists())

    def test_harness_populates_raw_behavioral_oracle_feedback(self) -> None:
        checks = iter([
            (False, False, "model_check_error"),
            (True, True, "none"),
        ])

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
        observations = result.get("observations", [])
        self.assertGreater(len(observations), 0)
        for obs in observations:
            event = obs.get("event", {})
            self.assertIn("raw_behavioral_oracle_feedback", event)
            feedback = event["raw_behavioral_oracle_feedback"]
            self.assertIsInstance(feedback, str)
            self.assertNotEqual(feedback, "")
            if "PASS" in feedback:
                self.assertIn("behavioral_oracle_verdict: PASS", feedback)
                self.assertIn("checkModel: PASS", feedback)


if __name__ == "__main__":
    unittest.main()
