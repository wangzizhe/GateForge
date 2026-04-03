from __future__ import annotations

import unittest

from gateforge.agent_modelica_v0_3_15_baseline_gate import _baseline_band_status, _summarize_rows
from gateforge.agent_modelica_v0_3_15_closeout import _summary_text
from gateforge.agent_modelica_v0_3_15_replay_evidence import _decide, _metric_delta


class AgentModelicaV0315GateAndCloseoutTests(unittest.TestCase):
    def test_baseline_band_status_distinguishes_saturated_and_in_band(self) -> None:
        self.assertEqual(_baseline_band_status({"pass_rate_pct": 100.0, "progressive_solve_rate_pct": 100.0, "dead_end_or_non_progress_rate_pct": 0.0}), "baseline_saturated")
        self.assertEqual(_baseline_band_status({"pass_rate_pct": 50.0, "progressive_solve_rate_pct": 37.5, "dead_end_or_non_progress_rate_pct": 50.0}), "baseline_in_band")
        self.assertEqual(_baseline_band_status({"pass_rate_pct": 12.5, "progressive_solve_rate_pct": 0.0, "dead_end_or_non_progress_rate_pct": 87.5}), "baseline_too_hard")

    def test_summarize_rows_computes_band_metrics(self) -> None:
        summary = _summarize_rows(
            [
                {"verdict": "PASS", "progressive_solve": True, "rounds_used": 4},
                {"verdict": "PASS", "progressive_solve": False, "rounds_used": 5},
                {"verdict": "FAIL", "progressive_solve": False, "rounds_used": 2},
            ]
        )
        self.assertEqual(summary["pass_rate_pct"], 66.7)
        self.assertEqual(summary["progressive_solve_rate_pct"], 33.3)
        self.assertEqual(summary["avg_rounds_on_pass"], 4.5)

    def test_metric_delta_and_decision_follow_replay_sensitive_labels(self) -> None:
        baseline_gate = {
            "decision": "replay_sensitive_eval_ready",
            "admitted_baseline": {
                "pass_rate_pct": 50.0,
                "progressive_solve_rate_pct": 37.5,
                "avg_rounds_on_pass": 4.0,
                "dead_end_or_non_progress_rate_pct": 62.5,
            },
        }
        replay = {
            "pass_rate_pct": 62.5,
            "progressive_solve_rate_pct": 50.0,
            "avg_rounds_on_pass": 3.0,
            "dead_end_or_non_progress_rate_pct": 50.0,
            "replay_hit_rate_pct": 75.0,
        }
        delta = _metric_delta(baseline_gate["admitted_baseline"], replay)
        self.assertEqual(delta["success_rate_pct_delta"], 12.5)
        self.assertEqual(_decide(baseline_gate, replay), "replay_sensitive_gain_confirmed")
        weak = dict(replay)
        weak["pass_rate_pct"] = 50.0
        weak["progressive_solve_rate_pct"] = 37.5
        weak["avg_rounds_on_pass"] = 4.0
        self.assertEqual(_decide(baseline_gate, weak), "replay_sensitive_eval_built_but_gain_weak")
        self.assertEqual(_decide({"decision": "replay_sensitive_eval_not_ready", "admitted_baseline": {}}, replay), "replay_sensitive_eval_not_ready")

    def test_summary_text_reflects_closeout_classification(self) -> None:
        self.assertIn("measurable gain", _summary_text("replay_sensitive_gain_confirmed", {}, {}))
        self.assertIn("replay deltas remained weak", _summary_text("replay_sensitive_eval_built_but_gain_weak", {}, {}))
        self.assertIn("did not produce a replay-sensitive admitted slice", _summary_text("replay_sensitive_eval_not_ready", {}, {}))


if __name__ == "__main__":
    unittest.main()
