from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_14_replay_evidence import _decide, _metric_delta


class AgentModelicaV0314ReplayEvidenceTests(unittest.TestCase):
    def test_metric_delta_reports_main_comparisons(self) -> None:
        baseline = {
            "pass_rate_pct": 50.0,
            "progressive_solve_rate_pct": 37.5,
            "avg_rounds_on_pass": 4.0,
            "dead_end_or_non_progress_rate_pct": 62.5,
        }
        replay = {
            "pass_rate_pct": 62.5,
            "progressive_solve_rate_pct": 50.0,
            "avg_rounds_on_pass": 3.0,
            "dead_end_or_non_progress_rate_pct": 50.0,
        }
        delta = _metric_delta(baseline, replay)
        self.assertEqual(delta["success_rate_pct_delta"], 12.5)
        self.assertEqual(delta["progressive_solve_rate_pct_delta"], 12.5)
        self.assertEqual(delta["avg_rounds_on_pass_delta"], -1.0)

    def test_decide_requires_runtime_gain_and_replay_hit(self) -> None:
        baseline = {"pass_rate_pct": 50.0, "progressive_solve_rate_pct": 37.5, "avg_rounds_on_pass": 4.0}
        replay = {"pass_rate_pct": 62.5, "progressive_solve_rate_pct": 50.0, "avg_rounds_on_pass": 3.0, "replay_hit_rate_pct": 75.0}
        self.assertEqual(_decide(baseline, replay), "replay_gain_confirmed")
        self.assertEqual(_decide(baseline, {"pass_rate_pct": 50.0, "progressive_solve_rate_pct": 37.5, "avg_rounds_on_pass": 4.0, "replay_hit_rate_pct": 50.0}), "replay_operational_but_no_clear_gain")
        self.assertEqual(_decide(baseline, {"pass_rate_pct": 50.0, "progressive_solve_rate_pct": 37.5, "avg_rounds_on_pass": 4.0, "replay_hit_rate_pct": 0.0}), "replay_not_yet_operational")


if __name__ == "__main__":
    unittest.main()
