import unittest

from gateforge.agent_modelica_l5_eval_v1 import _summarize_run_results


class AgentModelicaL5EvalQualityV1Tests(unittest.TestCase):
    def test_summarize_run_results_includes_quality_and_contributions(self) -> None:
        payload = {
            "records": [
                {
                    "passed": True,
                    "rounds_used": 1,
                    "elapsed_sec": 0.2,
                    "repair_quality_score": 1.0,
                    "action_contributions": [{"contribution": "advancing"}],
                    "hard_checks": {"physics_contract_pass": True, "regression_pass": True},
                    "attempts": [],
                },
                {
                    "passed": False,
                    "rounds_used": 2,
                    "elapsed_sec": 0.5,
                    "repair_quality_score": 0.4,
                    "action_contributions": [{"contribution": "neutral"}, {"contribution": "regressing"}],
                    "hard_checks": {"physics_contract_pass": False, "regression_pass": False},
                    "attempts": [],
                },
            ]
        }
        summary = _summarize_run_results(payload)
        self.assertEqual(summary["median_quality_score"], 0.7)
        self.assertEqual(summary["action_contribution_distribution"]["advancing"], 1)
        self.assertEqual(summary["action_contribution_distribution"]["neutral"], 1)
        self.assertEqual(summary["action_contribution_distribution"]["regressing"], 1)


if __name__ == "__main__":
    unittest.main()
