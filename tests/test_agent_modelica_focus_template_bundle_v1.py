import unittest

from gateforge.agent_modelica_focus_template_bundle_v1 import build_focus_template_bundle


class AgentModelicaFocusTemplateBundleV1Tests(unittest.TestCase):
    def test_build_bundle_from_top2_queue(self) -> None:
        queue = {
            "queue": [
                {"rank": 1, "failure_type": "simulate_error", "gate_break_reason": "regression_fail", "priority_score": 34.0},
                {"rank": 2, "failure_type": "semantic_regression", "gate_break_reason": "physics_contract_fail", "priority_score": 25.0},
            ]
        }
        payload = build_focus_template_bundle(queue_payload=queue, top_k=2)
        self.assertEqual(int(payload.get("template_count", 0)), 2)
        rows = payload.get("templates") if isinstance(payload.get("templates"), list) else []
        self.assertEqual(str(rows[0].get("failure_type") or ""), "simulate_error")
        self.assertTrue(str(rows[0].get("template_id") or "").startswith("tpl_"))
        self.assertGreaterEqual(int(rows[0].get("focus_actions_count", 0)), 1)

    def test_bundle_propagates_strategy_signal_scores(self) -> None:
        queue = {
            "queue": [
                {
                    "rank": 1,
                    "failure_type": "model_check_error",
                    "gate_break_reason": "check_model_fail",
                    "priority_score": 20.0,
                    "strategy_signal_treatment_score": 0.22,
                    "strategy_signal_delta_score": -0.12,
                }
            ]
        }
        payload = build_focus_template_bundle(queue_payload=queue, top_k=1)
        rows = payload.get("templates") if isinstance(payload.get("templates"), list) else []
        self.assertEqual(len(rows), 1)
        self.assertEqual(float(rows[0].get("strategy_signal_treatment_score", 0.0)), 0.22)
        self.assertEqual(float(rows[0].get("strategy_signal_delta_score", 0.0)), -0.12)


if __name__ == "__main__":
    unittest.main()
