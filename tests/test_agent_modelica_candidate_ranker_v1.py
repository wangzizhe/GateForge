"""Tests for agent_modelica_candidate_ranker_v1.

Pure unit tests with an injected mock OMC runner. No Docker, no LLM, no network.
Covers:
  - eq/var count extraction from OMC text
  - error count from OMC text
  - score computation ordering
  - evaluate_candidate handles empty / None patched_text
  - evaluate_candidate handles OMC runner exceptions (records -inf)
  - rank_candidates orders descending and is stable on ties
"""
import math
import unittest

from gateforge.agent_modelica_candidate_ranker_v1 import (
    RankedCandidate,
    _compute_score,
    _count_errors,
    _extract_eq_var_counts,
    evaluate_candidate,
    rank_candidates,
)


class TestExtractEqVarCounts(unittest.TestCase):
    def test_standard_omc_format(self) -> None:
        text = "Class Foo has 12 equation(s) and 15 variable(s)."
        eq, var = _extract_eq_var_counts(text)
        self.assertEqual(eq, 12)
        self.assertEqual(var, 15)

    def test_balanced(self) -> None:
        text = "Class Foo has 8 equation(s) and 8 variable(s)."
        eq, var = _extract_eq_var_counts(text)
        self.assertEqual((eq, var), (8, 8))

    def test_missing_returns_none_pair(self) -> None:
        eq, var = _extract_eq_var_counts("nothing relevant")
        self.assertIsNone(eq)
        self.assertIsNone(var)

    def test_empty_returns_none_pair(self) -> None:
        eq, var = _extract_eq_var_counts("")
        self.assertIsNone(eq)
        self.assertIsNone(var)


class TestCountErrors(unittest.TestCase):
    def test_no_errors(self) -> None:
        self.assertEqual(_count_errors("All good"), 0)

    def test_single_error_line(self) -> None:
        self.assertEqual(_count_errors("Error: variable X not determined"), 1)

    def test_multiple_error_lines(self) -> None:
        text = "Error: A\nWarning: ignore\nError: B\nError: C"
        self.assertEqual(_count_errors(text), 3)

    def test_empty(self) -> None:
        self.assertEqual(_count_errors(""), 0)


class TestComputeScore(unittest.TestCase):
    def test_check_pass_dominates(self) -> None:
        s_pass = _compute_score(check_pass=True, deficit=10, error_count=100)
        s_fail = _compute_score(check_pass=False, deficit=0, error_count=0)
        self.assertGreater(s_pass, s_fail)

    def test_smaller_deficit_wins(self) -> None:
        s_small = _compute_score(check_pass=False, deficit=1, error_count=0)
        s_big = _compute_score(check_pass=False, deficit=5, error_count=0)
        self.assertGreater(s_small, s_big)

    def test_fewer_errors_wins(self) -> None:
        s_few = _compute_score(check_pass=False, deficit=0, error_count=1)
        s_many = _compute_score(check_pass=False, deficit=0, error_count=10)
        self.assertGreater(s_few, s_many)

    def test_deficit_absolute_value(self) -> None:
        s_neg = _compute_score(check_pass=False, deficit=-3, error_count=0)
        s_pos = _compute_score(check_pass=False, deficit=3, error_count=0)
        self.assertEqual(s_neg, s_pos)

    def test_none_deficit_no_penalty(self) -> None:
        score = _compute_score(check_pass=False, deficit=None, error_count=2)
        self.assertEqual(score, -2.0)


class TestEvaluateCandidate(unittest.TestCase):
    def test_check_pass_path(self) -> None:
        runner = lambda _: (True, "Class Foo has 5 equation(s) and 5 variable(s).\ncheck completed")
        rc = evaluate_candidate(
            candidate_id=0,
            patched_text="model Foo end Foo;",
            llm_error="",
            provider="gemini",
            temperature_used=0.2,
            run_omc=runner,
        )
        self.assertTrue(rc.check_pass)
        self.assertEqual(rc.equation_count, 5)
        self.assertEqual(rc.variable_count, 5)
        self.assertEqual(rc.deficit, 0)
        self.assertEqual(rc.error_count, 0)
        self.assertEqual(rc.score, 1000.0)

    def test_check_fail_with_deficit(self) -> None:
        omc = "Class Foo has 4 equation(s) and 6 variable(s).\nError: X not determined"
        runner = lambda _: (False, omc)
        rc = evaluate_candidate(
            candidate_id=1,
            patched_text="model Foo end Foo;",
            llm_error="",
            provider="gemini",
            temperature_used=0.5,
            run_omc=runner,
        )
        self.assertFalse(rc.check_pass)
        self.assertEqual(rc.deficit, 2)
        self.assertEqual(rc.error_count, 1)
        # 0 - 10*2 - 1 = -21
        self.assertEqual(rc.score, -21.0)

    def test_empty_patched_text_sinks(self) -> None:
        rc = evaluate_candidate(
            candidate_id=2,
            patched_text="",
            llm_error="",
            provider="gemini",
            temperature_used=0.2,
            run_omc=lambda _: (True, ""),  # never called
        )
        self.assertEqual(rc.score, float("-inf"))
        self.assertFalse(rc.check_pass)
        self.assertEqual(rc.llm_error, "empty_patched_text")

    def test_none_patched_text_sinks(self) -> None:
        rc = evaluate_candidate(
            candidate_id=3,
            patched_text=None,
            llm_error="api_timeout",
            provider="gemini",
            temperature_used=None,
            run_omc=lambda _: (True, ""),
        )
        self.assertEqual(rc.score, float("-inf"))
        self.assertEqual(rc.llm_error, "api_timeout")

    def test_runner_exception_sinks_to_minus_inf(self) -> None:
        def _boom(_: str):
            raise RuntimeError("docker dead")
        rc = evaluate_candidate(
            candidate_id=4,
            patched_text="model Foo end Foo;",
            llm_error="",
            provider="gemini",
            temperature_used=0.2,
            run_omc=_boom,
        )
        self.assertEqual(rc.score, float("-inf"))
        self.assertIn("omc_runner_exception", rc.omc_output)
        self.assertIn("RuntimeError", rc.omc_output)


class TestRankCandidates(unittest.TestCase):
    def _runner_factory(self, mapping: dict[str, tuple[bool, str]]):
        return lambda text: mapping[text]

    def test_empty_input(self) -> None:
        self.assertEqual(rank_candidates([], run_omc=lambda _: (True, "")), [])

    def test_orders_by_score_desc(self) -> None:
        mapping = {
            "passing":  (True,  "Class Foo has 3 equation(s) and 3 variable(s).\ncheck completed"),
            "deficit1": (False, "Class Foo has 2 equation(s) and 3 variable(s).\nError: X"),
            "deficit3": (False, "Class Foo has 2 equation(s) and 5 variable(s).\nError: A\nError: B"),
        }
        candidates = [
            {"patched_text": "deficit3", "llm_error": "", "provider": "gemini", "temperature_used": 0.8},
            {"patched_text": "passing",  "llm_error": "", "provider": "gemini", "temperature_used": 0.2},
            {"patched_text": "deficit1", "llm_error": "", "provider": "gemini", "temperature_used": 0.5},
        ]
        ranked = rank_candidates(candidates, run_omc=self._runner_factory(mapping))
        self.assertEqual(ranked[0].patched_text, "passing")
        self.assertEqual(ranked[1].patched_text, "deficit1")
        self.assertEqual(ranked[2].patched_text, "deficit3")

    def test_failed_candidates_sink_to_bottom(self) -> None:
        mapping = {"good": (True, "Class Foo has 1 equation(s) and 1 variable(s).\ncheck completed")}
        candidates = [
            {"patched_text": None,    "llm_error": "api_err", "provider": "gemini"},
            {"patched_text": "good",  "llm_error": "",        "provider": "gemini"},
            {"patched_text": "",      "llm_error": "empty",   "provider": "gemini"},
        ]
        ranked = rank_candidates(candidates, run_omc=self._runner_factory(mapping))
        self.assertEqual(ranked[0].patched_text, "good")
        self.assertTrue(math.isinf(ranked[1].score) and ranked[1].score < 0)
        self.assertTrue(math.isinf(ranked[2].score) and ranked[2].score < 0)

    def test_to_dict_finite_score(self) -> None:
        rc = RankedCandidate(
            candidate_id=0, patched_text="x", llm_error="", provider="gemini",
            temperature_used=0.2, check_pass=True, equation_count=3, variable_count=3,
            deficit=0, error_count=0, omc_output="abc", score=1000.0,
        )
        d = rc.to_dict()
        self.assertEqual(d["score"], 1000.0)
        self.assertEqual(d["omc_output_length"], 3)

    def test_to_dict_minus_inf_score_becomes_none(self) -> None:
        rc = RankedCandidate(
            candidate_id=0, patched_text=None, llm_error="x", provider="gemini",
            temperature_used=None, check_pass=False, equation_count=None, variable_count=None,
            deficit=None, error_count=0, omc_output="", score=float("-inf"),
        )
        d = rc.to_dict()
        self.assertIsNone(d["score"])


if __name__ == "__main__":
    unittest.main()
