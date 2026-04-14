"""Tests for v0.19.0 foundation: taxonomy, stop signal, trajectory schema."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from gateforge.distribution_alignment_v0_19_0 import build_distribution_alignment_artifact
from gateforge.mutation_taxonomy_v0_19_0 import (
    MUTATION_TAXONOMY,
    TAXONOMY_FROZEN,
    TAXONOMY_IDS,
)
from gateforge.stop_signal_v0_19_0 import (
    HARD_CAP_TURNS,
    check_cycling,
    check_stalled,
    check_stop,
    check_timeout,
)
from gateforge.trajectory_schema_v0_19_0 import (
    SCHEMA_VERSION_SUMMARY,
    SCHEMA_VERSION_TURN,
    compute_progressive_solve,
    validate_summary_record,
    validate_turn_record,
)


class TestTaxonomy(unittest.TestCase):
    def test_taxonomy_frozen(self):
        """Validates the final committed state: TAXONOMY_FROZEN = True, all 6 categories present.
        Note: TAXONOMY_FROZEN starts as False during pre-alignment draft; this test validates
        the final committed state after the distribution alignment gate has passed.
        """
        self.assertTrue(TAXONOMY_FROZEN)
        self.assertEqual(len(MUTATION_TAXONOMY), 6)
        for tid in ("T1", "T2", "T3", "T4", "T5", "T6"):
            self.assertIn(tid, TAXONOMY_IDS)

    def test_taxonomy_entries_have_required_fields(self):
        for tid, entry in MUTATION_TAXONOMY.items():
            for field in ("name", "description", "expected_difficulty"):
                self.assertIn(field, entry, f"T{tid} missing field {field}")


class TestStopSignal(unittest.TestCase):
    def test_stop_hard_cap(self):
        should_stop, reason = check_stop(
            turn_id=HARD_CAP_TURNS,
            current_error="some error",
            current_patch="+ x = 1;",
            prior_errors=["different error"],
            prior_patches=["+ y = 2;"],
        )
        self.assertTrue(should_stop)
        self.assertEqual(reason, "timeout")

    def test_check_timeout_true(self):
        self.assertTrue(check_timeout(HARD_CAP_TURNS))
        self.assertTrue(check_timeout(HARD_CAP_TURNS + 1))

    def test_check_timeout_false(self):
        self.assertFalse(check_timeout(HARD_CAP_TURNS - 1))
        self.assertFalse(check_timeout(1))

    def test_stop_stalled(self):
        error = "Error: variable x is not defined"
        should_stop, reason = check_stop(
            turn_id=2,
            current_error=error,
            current_patch="+ x = 1;",
            prior_errors=[error],
            prior_patches=["+ y = 2;"],
        )
        self.assertTrue(should_stop)
        self.assertEqual(reason, "stalled")

    def test_stop_not_stalled_on_first_turn(self):
        """Single error occurrence does not trigger stalled."""
        should_stop, reason = check_stop(
            turn_id=1,
            current_error="Error: variable x is not defined",
            current_patch="+ x = 1;",
            prior_errors=[],
            prior_patches=[],
        )
        self.assertFalse(should_stop)
        self.assertIsNone(reason)

    def test_stop_not_stalled_when_errors_differ(self):
        should_stop, reason = check_stop(
            turn_id=2,
            current_error="Error: variable y is not defined",
            current_patch="+ y = 2;",
            prior_errors=["Error: variable x is not defined"],
            prior_patches=["+ x = 1;"],
        )
        self.assertFalse(should_stop)
        self.assertIsNone(reason)

    def test_stop_cycling(self):
        """Identical patch proposed again → Jaccard = 1.0 > 0.85 → cycling triggered."""
        patch = "+ Real x = 1.0;\n+ Real y = 2.0;\n+ Real z = 3.0;"
        should_stop, reason = check_stop(
            turn_id=3,
            current_error="Error: new error",
            current_patch=patch,
            prior_errors=["Error: old error"],
            prior_patches=[patch],  # same patch as before
        )
        self.assertTrue(should_stop)
        self.assertEqual(reason, "cycling")

    def test_stop_not_cycling_below_threshold(self):
        """Patches with entirely different tokens → Jaccard = 0.0 → no cycling."""
        patch_a = "+ Real x = 1.0;\n+ Real y = 2.0;"
        patch_b = "+ parameter Integer n = 42;\n+ Boolean flag = true;"
        should_stop, reason = check_stop(
            turn_id=3,
            current_error="Error: new error",
            current_patch=patch_a,
            prior_errors=["Error: old error"],
            prior_patches=[patch_b],
        )
        self.assertFalse(should_stop)
        self.assertIsNone(reason)

    def test_check_stalled_direct(self):
        self.assertTrue(check_stalled("same error", ["same error"]))
        self.assertFalse(check_stalled("new error", ["old error"]))
        self.assertFalse(check_stalled("any error", []))

    def test_check_cycling_ignores_reasoning_text(self):
        """Reasoning text outside diff hunks must not affect cycling detection."""
        patch_with_reasoning = (
            "I think the issue is the unit.\n"
            "+ Real x(unit=\"kg\") = 1.0;\n"
            "This should fix the problem."
        )
        patch_different = "+ Real y(unit=\"m\") = 5.0;\n+ Real z = 3.14;"
        self.assertFalse(check_cycling(patch_with_reasoning, [patch_different]))


class TestTrajectorySchema(unittest.TestCase):
    def _make_turn_record(self, **overrides) -> dict:
        base = {
            "schema_version": SCHEMA_VERSION_TURN,
            "task_id": "task_001",
            "turn_id": 1,
            "prompt": {"system": "sys", "user": "usr"},
            "llm_response": {
                "raw": "full response text",
                "parsed_patch": "+ x = 1;",
                "parsed_reasoning": "I think...",
            },
            "execution": {
                "simulation_status": "FAIL",
                "error_message": "Error: x not defined",
                "error_class": "T1",
                "error_stage": "stage_2",
            },
            "turn_outcome": "partial_progress",
        }
        base.update(overrides)
        return base

    def _make_summary_record(self, **overrides) -> dict:
        base = {
            "schema_version": SCHEMA_VERSION_SUMMARY,
            "task_id": "task_001",
            "total_turns": 3,
            "termination_reason": "success",
            "final_outcome": "success",
            "progressive_solve": True,
            "turn_outcomes": ["partial_progress", "partial_progress", "success"],
        }
        base.update(overrides)
        return base

    def test_schema_turn_record_required_fields(self):
        record = self._make_turn_record()
        errors = validate_turn_record(record)
        self.assertEqual(errors, [], f"unexpected errors: {errors}")

    def test_schema_turn_record_missing_field(self):
        record = self._make_turn_record()
        del record["turn_outcome"]
        errors = validate_turn_record(record)
        self.assertTrue(any("turn_outcome" in e for e in errors))

    def test_schema_summary_progressive_solve_true(self):
        record = self._make_summary_record(
            turn_outcomes=["partial_progress", "partial_progress", "success"],
            final_outcome="success",
            progressive_solve=True,
        )
        errors = validate_summary_record(record)
        self.assertEqual(errors, [], f"unexpected errors: {errors}")

    def test_schema_summary_progressive_solve_false_first_turn_success(self):
        """First-turn success → progressive_solve = False."""
        record = self._make_summary_record(
            turn_outcomes=["success"],
            final_outcome="success",
            progressive_solve=False,
        )
        errors = validate_summary_record(record)
        self.assertEqual(errors, [], f"unexpected errors: {errors}")

    def test_schema_summary_progressive_solve_false_failure(self):
        """Final failure → progressive_solve = False regardless of intermediate progress."""
        record = self._make_summary_record(
            turn_outcomes=["partial_progress", "no_progress", "gave_up"],
            final_outcome="failure",
            termination_reason="timeout",
            progressive_solve=False,
        )
        errors = validate_summary_record(record)
        self.assertEqual(errors, [], f"unexpected errors: {errors}")

    def test_schema_summary_progressive_solve_mismatch_flagged(self):
        """progressive_solve value inconsistent with turn_outcomes is caught."""
        record = self._make_summary_record(
            turn_outcomes=["success"],
            final_outcome="success",
            progressive_solve=True,  # wrong: first turn was success
        )
        errors = validate_summary_record(record)
        self.assertTrue(any("progressive_solve" in e for e in errors))

    def test_compute_progressive_solve(self):
        self.assertTrue(compute_progressive_solve(
            ["partial_progress", "success"], "success"
        ))
        self.assertFalse(compute_progressive_solve(
            ["success"], "success"
        ))
        self.assertFalse(compute_progressive_solve(
            ["partial_progress", "gave_up"], "failure"
        ))
        self.assertFalse(compute_progressive_solve(
            ["no_progress", "success"], "success"
        ))


class TestDistributionAlignment(unittest.TestCase):
    def test_distribution_alignment_artifact_passes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            payload = build_distribution_alignment_artifact(out_dir=tmp)
            summary_path = Path(tmp) / "summary.json"
            self.assertTrue(summary_path.exists())
            self.assertEqual(json.loads(summary_path.read_text(encoding="utf-8"))["status"], "PASS")

        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["sample_count"], 30)
        self.assertGreaterEqual(payload["overlap"], 0.70)
        self.assertTrue(payload["threshold_passed"])
        self.assertEqual(len(payload["rows"]), 30)

    def test_distribution_alignment_records_uncovered_clusters(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            payload = build_distribution_alignment_artifact(out_dir=tmp)

        self.assertIn("component_name_hallucination", payload["uncovered_clusters"])
        self.assertIn("control_architecture_omission", payload["uncovered_clusters"])
        self.assertEqual(payload["largest_uncovered_cluster"], "component_name_hallucination")


class TestCloseout(unittest.TestCase):
    def test_closeout_pass(self):
        import tempfile
        from gateforge.agent_modelica_v0_19_0_closeout import build_v190_closeout
        from gateforge.distribution_alignment_v0_19_0 import build_distribution_alignment_artifact

        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as align_tmp:
            payload = build_distribution_alignment_artifact(out_dir=align_tmp)
            self.assertEqual(payload["status"], "PASS")
            result = build_v190_closeout(
                out_dir=tmp,
                distribution_alignment_summary_path=str(Path(align_tmp) / "summary.json"),
            )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["conclusion"]["version_decision"], "v0_19_0_foundation_ready")
        self.assertTrue(result["conclusion"]["taxonomy_frozen"])
        self.assertTrue(result["conclusion"]["stop_signal_frozen"])
        self.assertTrue(result["conclusion"]["trajectory_schema_frozen"])
        self.assertEqual(result["conclusion"]["distribution_alignment_status"], "PASS")


if __name__ == "__main__":
    unittest.main()
