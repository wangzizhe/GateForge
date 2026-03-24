"""Tests for agent_modelica_decision_quality_gate_v1."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_decision_quality_gate_v1 import evaluate_gate


def _summary(
    *,
    first_plan_correct_pct: float = 60.0,
    failed_count: int = 2,
    total_tasks: int = 10,
    median_wasted_rounds: float = 1.0,
) -> dict:
    """Build a synthetic attribution summary for testing."""
    return {
        "schema_version": "agent_modelica_decision_attribution_v1",
        "total_tasks": total_tasks,
        "causal_path_distribution": {
            "direct": total_tasks - failed_count - 2,
            "exhaustive": 2,
            "replan_corrected": 0,
            "guided_search": 0,
            "failed": failed_count,
        },
        "first_plan_correct_pct": first_plan_correct_pct,
        "replan_corrected_pct": 0.0,
        "llm_decisive_pct": 0.0,
        "median_rounds_to_success": 2.0,
        "median_wasted_rounds": median_wasted_rounds,
        "causal_path_by_failure_type": {},
    }


class TestAllPass(unittest.TestCase):
    def test_all_pass(self) -> None:
        result = evaluate_gate(
            _summary(first_plan_correct_pct=60.0, failed_count=2, median_wasted_rounds=1.0),
            min_first_plan_correct_pct=40.0,
            max_failed_pct=30.0,
            max_median_wasted_rounds=2.0,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["checks"]["first_plan_quality"]["pass"])
        self.assertTrue(result["checks"]["failure_rate"]["pass"])
        self.assertTrue(result["checks"]["round_efficiency"]["pass"])

    def test_schema_version(self) -> None:
        result = evaluate_gate(_summary())
        self.assertEqual(result["schema_version"], "agent_modelica_decision_quality_gate_v1")

    def test_checks_have_actual_and_threshold(self) -> None:
        result = evaluate_gate(
            _summary(first_plan_correct_pct=50.0),
            min_first_plan_correct_pct=40.0,
        )
        check = result["checks"]["first_plan_quality"]
        self.assertAlmostEqual(check["actual"], 50.0)
        self.assertAlmostEqual(check["threshold"], 40.0)


class TestFirstPlanBelowThreshold(unittest.TestCase):
    def test_needs_review_when_first_plan_low(self) -> None:
        result = evaluate_gate(
            _summary(first_plan_correct_pct=30.0),
            min_first_plan_correct_pct=40.0,
            max_failed_pct=30.0,
            max_median_wasted_rounds=2.0,
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertFalse(result["checks"]["first_plan_quality"]["pass"])
        self.assertIn("first-plan correctness", result["primary_reason"])

    def test_exactly_at_threshold_passes(self) -> None:
        result = evaluate_gate(
            _summary(first_plan_correct_pct=40.0),
            min_first_plan_correct_pct=40.0,
        )
        self.assertTrue(result["checks"]["first_plan_quality"]["pass"])


class TestHighFailureRate(unittest.TestCase):
    def test_needs_review_when_failure_rate_high(self) -> None:
        # 4 out of 10 = 40% failed > 30% threshold
        result = evaluate_gate(
            _summary(failed_count=4, total_tasks=10),
            min_first_plan_correct_pct=40.0,
            max_failed_pct=30.0,
            max_median_wasted_rounds=2.0,
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertFalse(result["checks"]["failure_rate"]["pass"])
        self.assertIn("failure rate", result["primary_reason"])

    def test_zero_tasks_gives_zero_failed_pct(self) -> None:
        result = evaluate_gate(
            _summary(total_tasks=0, failed_count=0),
            max_failed_pct=30.0,
        )
        self.assertTrue(result["checks"]["failure_rate"]["pass"])
        self.assertAlmostEqual(result["checks"]["failure_rate"]["actual"], 0.0)


class TestInefficientRounds(unittest.TestCase):
    def test_needs_review_when_too_many_wasted_rounds(self) -> None:
        result = evaluate_gate(
            _summary(median_wasted_rounds=3.0),
            min_first_plan_correct_pct=40.0,
            max_failed_pct=30.0,
            max_median_wasted_rounds=2.0,
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertFalse(result["checks"]["round_efficiency"]["pass"])
        self.assertIn("median wasted", result["primary_reason"])


class TestTwoFailuresIsFail(unittest.TestCase):
    def test_two_failed_checks_gives_fail(self) -> None:
        result = evaluate_gate(
            _summary(first_plan_correct_pct=10.0, failed_count=5, total_tasks=10),
            min_first_plan_correct_pct=40.0,
            max_failed_pct=30.0,
            max_median_wasted_rounds=2.0,
        )
        self.assertEqual(result["status"], "FAIL")

    def test_three_failed_checks_gives_fail(self) -> None:
        result = evaluate_gate(
            _summary(
                first_plan_correct_pct=10.0,
                failed_count=5,
                total_tasks=10,
                median_wasted_rounds=5.0,
            ),
            min_first_plan_correct_pct=40.0,
            max_failed_pct=30.0,
            max_median_wasted_rounds=2.0,
        )
        self.assertEqual(result["status"], "FAIL")


class TestCLIRoundtrip(unittest.TestCase):
    def test_cli_produces_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            attr_file = root / "attribution.json"
            out = root / "gate.json"
            report = root / "gate.md"

            attr_file.write_text(
                json.dumps(
                    {
                        "summary": _summary(
                            first_plan_correct_pct=55.0,
                            failed_count=2,
                            total_tasks=10,
                            median_wasted_rounds=1.5,
                        )
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_decision_quality_gate_v1",
                    "--decision-attribution", str(attr_file),
                    "--min-first-plan-correct-pct", "40",
                    "--max-failed-pct", "30",
                    "--max-median-wasted-rounds", "2.0",
                    "--out", str(out),
                    "--report-out", str(report),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(out.read_text())
            self.assertEqual(data["schema_version"], "agent_modelica_decision_quality_gate_v1")
            self.assertEqual(data["status"], "PASS")
            self.assertTrue(report.exists())


if __name__ == "__main__":
    unittest.main()
