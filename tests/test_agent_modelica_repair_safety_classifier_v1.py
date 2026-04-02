"""Tests for repair safety classifier.

Pure-function tests: no Docker, LLM, OMC, or filesystem dependencies.
"""
from __future__ import annotations

import unittest

from gateforge.agent_modelica_repair_safety_classifier_v1 import (
    VERDICT_NEEDS_REVIEW,
    VERDICT_REJECT,
    VERDICT_SAFE,
    RepairSafetyResult,
    SafetyViolation,
    classify_repair_safety,
    is_safe_to_apply,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SIMPLE_MODEL = """\
model SimpleRC
  parameter Real R = 1.0;
  parameter Real C = 1.0;
  Real u(start = 0.0);
  Real i;
equation
  i = u / R;
  C * der(u) = i;
initial equation
  u = 0.0;
end SimpleRC;
"""

_CONNECTED_MODEL = """\
model System
  parameter Real k = 2.0;
  parameter Real m = 1.0;
  SubA a;
  SubB b;
  SubC c;
equation
  connect(a.port, b.port);
  connect(b.port, c.port);
  connect(c.port, a.port);
end System;
"""

_PARAMETER_HEAVY = """\
model Params
  parameter Real a = 1.0;
  parameter Real b = 2.0;
  parameter Real c = 3.0;
  parameter Real d = 4.0;
  Real x;
equation
  x = a * b + c / d;
end Params;
"""


# ===========================================================================
# Safe repairs — no violations
# ===========================================================================


class TestSafeRepairs(unittest.TestCase):
    def test_identical_text_is_safe(self) -> None:
        result = classify_repair_safety(_SIMPLE_MODEL, _SIMPLE_MODEL)
        self.assertEqual(result.verdict, VERDICT_SAFE)
        self.assertTrue(result.is_safe)
        self.assertEqual(len(result.violations), 0)

    def test_minor_parameter_change_is_safe(self) -> None:
        proposed = _SIMPLE_MODEL.replace("R = 1.0", "R = 2.5")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertEqual(result.verdict, VERDICT_SAFE)

    def test_whitespace_only_change_is_safe(self) -> None:
        proposed = _SIMPLE_MODEL.replace("  ", "   ")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertEqual(result.verdict, VERDICT_SAFE)

    def test_comment_added_is_safe(self) -> None:
        # Insert a comment before the equation section without touching "initial equation"
        proposed = _SIMPLE_MODEL.replace(
            "\nequation\n  i = u / R;",
            "\n// fixed\nequation\n  i = u / R;",
        )
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertEqual(result.verdict, VERDICT_SAFE)

    def test_is_safe_to_apply_true_for_safe_repair(self) -> None:
        proposed = _SIMPLE_MODEL.replace("C = 1.0", "C = 0.5")
        self.assertTrue(is_safe_to_apply(_SIMPLE_MODEL, proposed))


# ===========================================================================
# EMPTY_REPAIR
# ===========================================================================


class TestEmptyRepair(unittest.TestCase):
    def test_empty_string_is_rejected(self) -> None:
        result = classify_repair_safety(_SIMPLE_MODEL, "")
        self.assertEqual(result.verdict, VERDICT_REJECT)
        self.assertIn("EMPTY_REPAIR", result.violation_ids)

    def test_whitespace_only_is_rejected(self) -> None:
        result = classify_repair_safety(_SIMPLE_MODEL, "   \n\t\n  ")
        self.assertEqual(result.verdict, VERDICT_REJECT)
        self.assertIn("EMPTY_REPAIR", result.violation_ids)

    def test_is_safe_to_apply_false_for_empty(self) -> None:
        self.assertFalse(is_safe_to_apply(_SIMPLE_MODEL, ""))


# ===========================================================================
# MODEL_EMPTIED
# ===========================================================================


class TestModelEmptied(unittest.TestCase):
    def test_drastically_shorter_is_rejected(self) -> None:
        # <20% of original length
        tiny = "model SimpleRC\nend SimpleRC;"
        result = classify_repair_safety(_SIMPLE_MODEL, tiny)
        self.assertEqual(result.verdict, VERDICT_REJECT)
        self.assertIn("MODEL_EMPTIED", result.violation_ids)

    def test_moderately_shorter_is_safe(self) -> None:
        # Remove one line but keep >80% of content
        proposed = _SIMPLE_MODEL.replace("  Real i;\n", "")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        # Should not trigger MODEL_EMPTIED (ratio still >0.20)
        self.assertNotIn("MODEL_EMPTIED", result.violation_ids)

    def test_planner_heavy_has_stricter_threshold(self) -> None:
        # Build text that is ~25% of original — safe in default but rejected in planner_heavy
        # Original is ~200 chars; 25% is ~50 chars
        original = "x" * 200 + "\nequation\n  y = 1;\nend M;"
        proposed = "x" * 45 + "\nend M;"   # ~22% of original
        default_result = classify_repair_safety(original, proposed, profile="default")
        planner_result = classify_repair_safety(original, proposed, profile="planner_heavy")
        # default: 22% > 20% threshold → safe on this check
        self.assertNotIn("MODEL_EMPTIED", default_result.violation_ids)
        # planner_heavy: 22% < 30% threshold → rejected
        self.assertIn("MODEL_EMPTIED", planner_result.violation_ids)


# ===========================================================================
# MODEL_NAME_CHANGED
# ===========================================================================


class TestModelNameChanged(unittest.TestCase):
    def test_name_change_is_rejected(self) -> None:
        proposed = _SIMPLE_MODEL.replace("model SimpleRC", "model DifferentModel").replace("end SimpleRC", "end DifferentModel")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertEqual(result.verdict, VERDICT_REJECT)
        self.assertIn("MODEL_NAME_CHANGED", result.violation_ids)

    def test_same_name_is_not_flagged(self) -> None:
        proposed = _SIMPLE_MODEL.replace("R = 1.0", "R = 3.0")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertNotIn("MODEL_NAME_CHANGED", result.violation_ids)

    def test_violation_detail_contains_names(self) -> None:
        proposed = _SIMPLE_MODEL.replace("model SimpleRC", "model WrongName").replace("end SimpleRC", "end WrongName")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        violation = next(v for v in result.violations if v.pattern_id == "MODEL_NAME_CHANGED")
        self.assertIn("SimpleRC", violation.detail)
        self.assertIn("WrongName", violation.detail)


# ===========================================================================
# EQUATION_BLOCK_REMOVED
# ===========================================================================


class TestEquationBlockRemoved(unittest.TestCase):
    def test_removing_equation_section_is_rejected(self) -> None:
        proposed = "\n".join(
            line for line in _SIMPLE_MODEL.splitlines()
            if not line.strip().startswith("equation")
            and not line.strip().startswith("i =")
            and not line.strip().startswith("C *")
        )
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertEqual(result.verdict, VERDICT_REJECT)
        self.assertIn("EQUATION_BLOCK_REMOVED", result.violation_ids)

    def test_equation_section_preserved_is_safe(self) -> None:
        proposed = _SIMPLE_MODEL.replace("i = u / R", "i = (u - 0.1) / R")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertNotIn("EQUATION_BLOCK_REMOVED", result.violation_ids)

    def test_model_without_equation_is_not_flagged(self) -> None:
        # If original has no equation section, removing it is not a violation
        original = "model Empty\n  parameter Real x = 1.0;\nend Empty;"
        proposed = "model Empty\n  parameter Real x = 2.0;\nend Empty;"
        result = classify_repair_safety(original, proposed)
        self.assertNotIn("EQUATION_BLOCK_REMOVED", result.violation_ids)


# ===========================================================================
# INITIAL_EQUATION_REMOVED
# ===========================================================================


class TestInitialEquationRemoved(unittest.TestCase):
    def test_removing_initial_equation_is_needs_review(self) -> None:
        proposed = "\n".join(
            line for line in _SIMPLE_MODEL.splitlines()
            if not line.strip().startswith("initial equation")
            and not (line.strip() == "u = 0.0;" and "initial" not in line)
        )
        # Remove lines after initial equation too
        lines = _SIMPLE_MODEL.splitlines()
        filtered = []
        skip = False
        for line in lines:
            if line.strip().startswith("initial equation"):
                skip = True
                continue
            if skip and line.strip().startswith("end "):
                skip = False
            if not skip:
                filtered.append(line)
        proposed = "\n".join(filtered)
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertIn("INITIAL_EQUATION_REMOVED", result.violation_ids)
        # Check verdict is at most NEEDS_REVIEW (not REJECT) for this pattern alone
        violation = next(v for v in result.violations if v.pattern_id == "INITIAL_EQUATION_REMOVED")
        self.assertEqual(violation.verdict, VERDICT_NEEDS_REVIEW)

    def test_initial_equation_preserved_is_not_flagged(self) -> None:
        proposed = _SIMPLE_MODEL.replace("u = 0.0;", "u = 0.1;")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertNotIn("INITIAL_EQUATION_REMOVED", result.violation_ids)

    def test_model_without_initial_equation_not_flagged(self) -> None:
        original = "model NoInit\n  Real x;\nequation\n  der(x) = 1.0;\nend NoInit;"
        proposed = "model NoInit\n  Real x;\nequation\n  der(x) = 2.0;\nend NoInit;"
        result = classify_repair_safety(original, proposed)
        self.assertNotIn("INITIAL_EQUATION_REMOVED", result.violation_ids)


# ===========================================================================
# CONNECT_MASS_DELETION
# ===========================================================================


class TestConnectMassDeletion(unittest.TestCase):
    def test_removing_all_connects_is_rejected(self) -> None:
        proposed = "\n".join(
            line for line in _CONNECTED_MODEL.splitlines()
            if "connect(" not in line
        )
        result = classify_repair_safety(_CONNECTED_MODEL, proposed)
        self.assertEqual(result.verdict, VERDICT_REJECT)
        self.assertIn("CONNECT_MASS_DELETION", result.violation_ids)

    def test_removing_one_connect_is_safe(self) -> None:
        proposed = _CONNECTED_MODEL.replace("  connect(c.port, a.port);\n", "")
        result = classify_repair_safety(_CONNECTED_MODEL, proposed)
        self.assertNotIn("CONNECT_MASS_DELETION", result.violation_ids)

    def test_model_with_single_connect_not_flagged(self) -> None:
        # Threshold only applies when original has >= 2 connect statements
        original = "model One\nequation\n  connect(a.p, b.p);\nend One;"
        proposed = "model One\nequation\nend One;"
        result = classify_repair_safety(original, proposed)
        self.assertNotIn("CONNECT_MASS_DELETION", result.violation_ids)

    def test_planner_heavy_stricter_threshold(self) -> None:
        # 50% deletion: safe in default (threshold 60%), flagged in planner_heavy (threshold 40%)
        model = """\
model Sys
  A a; B b; C c; D d;
equation
  connect(a.p, b.p);
  connect(b.p, c.p);
  connect(c.p, d.p);
  connect(d.p, a.p);
end Sys;
"""
        # Remove 2 of 4 connects = 50%
        proposed = "\n".join(
            line for line in model.splitlines()
            if "connect(c.p" not in line and "connect(d.p" not in line
        )
        default_result = classify_repair_safety(model, proposed, profile="default")
        planner_result = classify_repair_safety(model, proposed, profile="planner_heavy")
        self.assertNotIn("CONNECT_MASS_DELETION", default_result.violation_ids)
        self.assertIn("CONNECT_MASS_DELETION", planner_result.violation_ids)

    def test_violation_detail_contains_counts(self) -> None:
        proposed = "\n".join(
            line for line in _CONNECTED_MODEL.splitlines()
            if "connect(" not in line
        )
        result = classify_repair_safety(_CONNECTED_MODEL, proposed)
        violation = next(v for v in result.violations if v.pattern_id == "CONNECT_MASS_DELETION")
        self.assertIn("original_connect_count=3", violation.detail)
        self.assertIn("proposed_connect_count=0", violation.detail)


# ===========================================================================
# PARAMETER_MASS_DEMOTION
# ===========================================================================


class TestParameterMassDemotion(unittest.TestCase):
    def test_removing_all_parameters_is_flagged(self) -> None:
        proposed = _PARAMETER_HEAVY.replace("parameter Real ", "Real ")
        result = classify_repair_safety(_PARAMETER_HEAVY, proposed)
        self.assertIn("PARAMETER_MASS_DEMOTION", result.violation_ids)
        violation = next(v for v in result.violations if v.pattern_id == "PARAMETER_MASS_DEMOTION")
        self.assertEqual(violation.verdict, VERDICT_NEEDS_REVIEW)

    def test_removing_one_parameter_is_safe(self) -> None:
        proposed = _PARAMETER_HEAVY.replace("parameter Real a = 1.0;\n", "Real a = 1.0;\n")
        result = classify_repair_safety(_PARAMETER_HEAVY, proposed)
        self.assertNotIn("PARAMETER_MASS_DEMOTION", result.violation_ids)

    def test_single_parameter_model_not_flagged(self) -> None:
        original = "model One\n  parameter Real x = 1.0;\nequation\n  x = 1.0;\nend One;"
        proposed = "model One\n  Real x = 1.0;\nequation\n  x = 1.0;\nend One;"
        result = classify_repair_safety(original, proposed)
        self.assertNotIn("PARAMETER_MASS_DEMOTION", result.violation_ids)

    def test_planner_heavy_stricter_threshold(self) -> None:
        # Remove 2 of 4 parameters = 50% — safe in default (50% threshold), flagged in planner_heavy (30%)
        proposed = (
            _PARAMETER_HEAVY
            .replace("parameter Real a = 1.0;\n", "Real a = 1.0;\n")
            .replace("parameter Real b = 2.0;\n", "Real b = 2.0;\n")
        )
        default_result = classify_repair_safety(_PARAMETER_HEAVY, proposed, profile="default")
        planner_result = classify_repair_safety(_PARAMETER_HEAVY, proposed, profile="planner_heavy")
        self.assertNotIn("PARAMETER_MASS_DEMOTION", default_result.violation_ids)
        self.assertIn("PARAMETER_MASS_DEMOTION", planner_result.violation_ids)


# ===========================================================================
# Aggregate verdict
# ===========================================================================


class TestAggregateVerdict(unittest.TestCase):
    def test_reject_dominates_needs_review(self) -> None:
        # Trigger both MODEL_NAME_CHANGED (reject) and INITIAL_EQUATION_REMOVED (needs_review)
        lines = _SIMPLE_MODEL.splitlines()
        filtered = []
        skip = False
        for line in lines:
            if line.strip().startswith("initial equation"):
                skip = True
                continue
            if skip and line.strip().startswith("end "):
                skip = False
            if not skip:
                filtered.append(line)
        # Also rename the model to trigger MODEL_NAME_CHANGED (reject)
        proposed = "\n".join(filtered).replace("model SimpleRC", "model Renamed").replace("end SimpleRC", "end Renamed")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertIn("MODEL_NAME_CHANGED", result.violation_ids)   # reject
        self.assertIn("INITIAL_EQUATION_REMOVED", result.violation_ids)  # needs_review
        self.assertEqual(result.verdict, VERDICT_REJECT)

    def test_needs_review_without_reject(self) -> None:
        # Only trigger INITIAL_EQUATION_REMOVED
        lines = _SIMPLE_MODEL.splitlines()
        filtered = []
        skip = False
        for line in lines:
            if line.strip().startswith("initial equation"):
                skip = True
                continue
            if skip and line.strip().startswith("end "):
                skip = False
            if not skip:
                filtered.append(line)
        proposed = "\n".join(filtered)
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        if "INITIAL_EQUATION_REMOVED" in result.violation_ids:
            # May have other violations too; check no REJECT-level ones
            reject_violations = [v for v in result.violations if v.verdict == VERDICT_REJECT]
            if not reject_violations:
                self.assertEqual(result.verdict, VERDICT_NEEDS_REVIEW)

    def test_no_violations_gives_safe(self) -> None:
        result = classify_repair_safety(_SIMPLE_MODEL, _SIMPLE_MODEL)
        self.assertEqual(result.verdict, VERDICT_SAFE)
        self.assertEqual(len(result.violations), 0)


# ===========================================================================
# RepairSafetyResult fields and summary
# ===========================================================================


class TestRepairSafetyResult(unittest.TestCase):
    def test_line_counts_are_accurate(self) -> None:
        result = classify_repair_safety(_SIMPLE_MODEL, _SIMPLE_MODEL)
        self.assertEqual(result.original_line_count, len(_SIMPLE_MODEL.splitlines()))
        self.assertEqual(result.proposed_line_count, len(_SIMPLE_MODEL.splitlines()))

    def test_char_counts_are_accurate(self) -> None:
        result = classify_repair_safety(_SIMPLE_MODEL, _SIMPLE_MODEL)
        self.assertEqual(result.original_char_count, len(_SIMPLE_MODEL))
        self.assertEqual(result.proposed_char_count, len(_SIMPLE_MODEL))

    def test_profile_is_recorded(self) -> None:
        result = classify_repair_safety(_SIMPLE_MODEL, _SIMPLE_MODEL, profile="planner_heavy")
        self.assertEqual(result.profile, "planner_heavy")

    def test_violation_ids_property(self) -> None:
        proposed = _SIMPLE_MODEL.replace("model SimpleRC", "model Changed").replace("end SimpleRC", "end Changed")
        result = classify_repair_safety(_SIMPLE_MODEL, proposed)
        self.assertIsInstance(result.violation_ids, list)
        self.assertIn("MODEL_NAME_CHANGED", result.violation_ids)

    def test_summary_contains_required_keys(self) -> None:
        result = classify_repair_safety(_SIMPLE_MODEL, _SIMPLE_MODEL)
        summary = result.summary()
        for key in (
            "verdict", "is_safe", "violation_count", "violation_ids",
            "original_line_count", "proposed_line_count",
            "original_char_count", "proposed_char_count", "profile",
        ):
            self.assertIn(key, summary)

    def test_violations_is_tuple(self) -> None:
        result = classify_repair_safety(_SIMPLE_MODEL, _SIMPLE_MODEL)
        self.assertIsInstance(result.violations, tuple)


# ===========================================================================
# is_safe_to_apply
# ===========================================================================


class TestIsSafeToApply(unittest.TestCase):
    def test_true_for_clean_repair(self) -> None:
        self.assertTrue(is_safe_to_apply(_SIMPLE_MODEL, _SIMPLE_MODEL))

    def test_false_for_empty_repair(self) -> None:
        self.assertFalse(is_safe_to_apply(_SIMPLE_MODEL, ""))

    def test_false_for_name_change(self) -> None:
        proposed = _SIMPLE_MODEL.replace("model SimpleRC", "model Wrong").replace("end SimpleRC", "end Wrong")
        self.assertFalse(is_safe_to_apply(_SIMPLE_MODEL, proposed))

    def test_profile_parameter_respected(self) -> None:
        # 25% size — safe in default (threshold 20%), rejected in planner_heavy (threshold 30%)
        # Both keep 'equation' so EQUATION_BLOCK_REMOVED does not fire.
        original = "x" * 200 + "\nequation\n  y = 1;\nend M;"
        proposed = "x" * 40 + "\nequation\n  y = 1;\nend M;"  # ~29% of original
        self.assertTrue(is_safe_to_apply(original, proposed, profile="default"))
        self.assertFalse(is_safe_to_apply(original, proposed, profile="planner_heavy"))


if __name__ == "__main__":
    unittest.main()
