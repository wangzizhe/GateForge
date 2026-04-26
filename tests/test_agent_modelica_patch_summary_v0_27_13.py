from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_deepseek_frozen_harness_baseline_v0_27_0 import (
    BUILTIN_CASES,
    run_live_case,
)
from gateforge.agent_modelica_patch_summary_v0_27_13 import (
    build_patch_summary_contract_summary,
    generate_patch_summary,
    validate_patch_summary,
)


class PatchSummaryV02713Tests(unittest.TestCase):
    def test_no_changes_returns_signal(self) -> None:
        text = "model Demo\n  Real x;\nend Demo;"
        summary = generate_patch_summary(text, text)
        self.assertEqual(summary, "No structural changes detected.")

    def test_whitespace_only_diff_is_no_change(self) -> None:
        old = "model Demo\n  Real x;\nend Demo;"
        new = "\nmodel Demo\n  Real x;\nend Demo;\n"
        summary = generate_patch_summary(old, new)
        self.assertEqual(summary, "No structural changes detected.")

    def test_text_diff_but_same_signature(self) -> None:
        old = "model Demo\n  Real x;\nequation\n  x = 1;\nend Demo;"
        new = "model Demo\n  // comment added\n  Real x;\nequation\n  x = 1;\nend Demo;"
        summary = generate_patch_summary(old, new)
        self.assertIn("No structural changes detected", summary)
        self.assertIn("signature unchanged", summary.lower())

    def test_variable_added(self) -> None:
        old = "model Demo\n  Real x;\nend Demo;"
        new = "model Demo\n  Real x;\n  Real y;\nend Demo;"
        summary = generate_patch_summary(old, new)
        self.assertIn("Added variable: Real y", summary)

    def test_variable_removed(self) -> None:
        old = "model Demo\n  Real x;\n  Real y;\nend Demo;"
        new = "model Demo\n  Real x;\nend Demo;"
        summary = generate_patch_summary(old, new)
        self.assertIn("Removed variable: Real y", summary)

    def test_component_added(self) -> None:
        old = "model Demo\n  Real x;\nend Demo;"
        new = "model Demo\n  Resistor R1(R=1);\n  Real x;\nend Demo;"
        summary = generate_patch_summary(old, new)
        self.assertIn("Added component: Resistor R1", summary)

    def test_component_removed(self) -> None:
        old = "model Demo\n  Resistor R1(R=1);\n  Real x;\nend Demo;"
        new = "model Demo\n  Real x;\nend Demo;"
        summary = generate_patch_summary(old, new)
        self.assertIn("Removed component: Resistor R1", summary)

    def test_equation_added(self) -> None:
        old = "model Demo\n  Real x;\nequation\n  x = 0;\nend Demo;"
        new = "model Demo\n  Real x;\nequation\n  x = 0;\n  x = 1;\nend Demo;"
        summary = generate_patch_summary(old, new)
        self.assertIn("Added equation", summary)

    def test_equation_removed(self) -> None:
        old = "model Demo\n  Real x;\nequation\n  x = 0;\n  x = 1;\nend Demo;"
        new = "model Demo\n  Real x;\nequation\n  x = 0;\nend Demo;"
        summary = generate_patch_summary(old, new)
        self.assertIn("Removed equation", summary)

    def test_multiple_changes_includes_model_name(self) -> None:
        old = "model SmallRC\n  Real x;\nequation\n  x = 0;\nend SmallRC;"
        new = "model SmallRC\n  Real x;\n  Real y;\nequation\n  x = y;\n  y = 1;\nend SmallRC;"
        summary = generate_patch_summary(old, new)
        self.assertIn("Changed model: SmallRC", summary)
        self.assertIn("Added variable: Real y", summary)
        self.assertIn("Added equation", summary)
        self.assertIn("Removed equation", summary)

    def test_validate_accepts_clean_summary(self) -> None:
        errors = validate_patch_summary("Changed model: Demo\n- Added variable: Real x")
        self.assertEqual(errors, [])

    def test_validate_rejects_hint_terms(self) -> None:
        errors = validate_patch_summary("Changed model: Demo\n- You should fix the equation")
        self.assertIn("forbidden:you should", errors)

    def test_validate_rejects_root_cause(self) -> None:
        errors = validate_patch_summary("Changed model: Demo\n- Root cause: missing equation")
        self.assertIn("forbidden:root cause", errors)

    def test_validate_rejects_repair_hint(self) -> None:
        errors = validate_patch_summary("Changed model: Demo\n- repair_hint: add equation")
        self.assertIn("forbidden:repair_hint", errors)

    def test_validate_rejects_recommend(self) -> None:
        errors = validate_patch_summary("Changed model: Demo\n- recommend adding equation")
        self.assertIn("forbidden:recommend", errors)

    def test_empty_text_is_handled(self) -> None:
        old = ""
        new = "model Demo\n  Real x;\nend Demo;\n"
        summary = generate_patch_summary(old, new)
        self.assertIn("Changed model: Demo", summary)
        self.assertIn("Added variable: Real x", summary)

    def test_build_summary_writes_contract_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            summary = build_patch_summary_contract_summary(out_dir=out_dir)
            self.assertEqual(summary["status"], "PASS")
            self.assertFalse(summary["discipline"]["hint_terms_found"])
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "canonical_summary.txt").exists())

    def test_harness_populates_previous_patch_summary_in_observation(self) -> None:
        case = BUILTIN_CASES[0].copy()
        result = run_live_case(case, max_rounds=2)
        observations = result.get("observations", [])
        self.assertGreater(len(observations), 0)
        for obs in observations:
            event = obs.get("event", {})
            self.assertIn("previous_patch_summary", event)
            summary = event["previous_patch_summary"]
            self.assertIsInstance(summary, str)

    def test_harness_populates_change_summary_in_repair_history_prompt(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _format_repair_history

        history = [
            {
                "round": 1,
                "provider": "deepseek",
                "patched_text_present": True,
                "model_changed": True,
                "check_pass_after_patch": False,
                "check_pass": False,
                "input_omc_summary": "Error: missing equation",
                "post_patch_omc_summary": "Error: under-determined",
                "omc_summary": "Error: under-determined",
                "change_summary": "Changed model: Demo\n- Added variable: Real y",
            }
        ]
        prompt = _format_repair_history(history)
        self.assertIn("Changed model: Demo", prompt)
        self.assertIn("Added variable: Real y", prompt)
        self.assertNotIn("You modified the model", prompt)

    def test_repair_history_fallback_when_no_change_summary(self) -> None:
        from gateforge.agent_modelica_l2_plan_replan_engine_v1 import _format_repair_history

        history = [
            {
                "round": 1,
                "provider": "deepseek",
                "patched_text_present": True,
                "model_changed": True,
                "check_pass_after_patch": False,
                "check_pass": False,
                "input_omc_summary": "Error",
                "post_patch_omc_summary": "Error",
                "omc_summary": "Error",
            }
        ]
        prompt = _format_repair_history(history)
        self.assertIn("You modified the model", prompt)


if __name__ == "__main__":
    unittest.main()
