import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_retrieval_trajectory_v0_19_58.py"
SPEC = importlib.util.spec_from_file_location("run_retrieval_trajectory_v0_19_58", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AgentModelicaV01958RetrievalRunnerTests(unittest.TestCase):
    def test_compute_summary_adds_retrieval_metrics(self) -> None:
        results = [
            {
                "candidate_id": "case_a",
                "final_status": "pass",
                "rounds": [
                    {
                        "num_candidates": 5,
                        "any_check_pass": True,
                        "any_simulate_pass": True,
                        "coverage_check_pass": 2,
                        "coverage_simulate_pass": 1,
                        "retrieval_enabled": True,
                        "retrieval_latency_ms": 1.5,
                        "retrieval_hit_count": 3,
                        "retrieval_context_char_count": 220,
                    }
                ],
            },
            {
                "candidate_id": "case_b",
                "final_status": "fail",
                "rounds": [
                    {
                        "num_candidates": 5,
                        "any_check_pass": False,
                        "any_simulate_pass": False,
                        "coverage_check_pass": 0,
                        "coverage_simulate_pass": 0,
                        "retrieval_enabled": True,
                        "retrieval_latency_ms": 2.5,
                        "retrieval_hit_count": 2,
                        "retrieval_context_char_count": 180,
                    }
                ],
            },
        ]

        summary = MODULE.compute_summary("retrieval-c5", "hot", results)

        self.assertEqual(summary["dataset"], "hot")
        self.assertAlmostEqual(summary["avg_retrieval_latency_ms"], 2.0)
        self.assertAlmostEqual(summary["avg_retrieval_hit_count"], 2.5)
        self.assertAlmostEqual(summary["avg_retrieval_context_chars"], 200.0)
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["case_count"], 2)

    def test_resolve_cases_uses_hot_and_cold_defaults(self) -> None:
        hot_cases = MODULE._resolve_cases("hot", None)
        cold_cases = MODULE._resolve_cases("cold", None)

        self.assertEqual(len(hot_cases), 8)
        self.assertGreaterEqual(len(cold_cases), 5)
        self.assertEqual(set(hot_cases) & set(cold_cases), set())


if __name__ == "__main__":
    unittest.main()
