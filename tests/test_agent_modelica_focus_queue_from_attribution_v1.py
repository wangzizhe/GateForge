import unittest

from gateforge.agent_modelica_focus_queue_from_attribution_v1 import build_focus_queue


class AgentModelicaFocusQueueFromAttributionV1Tests(unittest.TestCase):
    def test_builds_top2_by_failure_type_and_gate_break(self) -> None:
        attribution = {
            "rows": [
                {"failure_type": "simulate_error", "gate_break_reason": "runtime_regression:2.8>2.4"},
                {"failure_type": "simulate_error", "gate_break_reason": "runtime_regression:2.9>2.4"},
                {"failure_type": "model_check_error", "gate_break_reason": "check_model_fail"},
                {"failure_type": "semantic_regression", "gate_break_reason": "physical_invariant_range_violated"},
                {"failure_type": "semantic_regression", "gate_break_reason": "physical_invariant_range_violated"},
                {"failure_type": "semantic_regression", "gate_break_reason": "runtime_regression:4.1>3.6"},
            ]
        }
        run_results = {
            "records": [
                {"task_id": "t1", "hard_checks": {"regression_pass": False}},
                {"task_id": "t2", "hard_checks": {"regression_pass": False}},
                {"task_id": "t3", "hard_checks": {"regression_pass": True}},
                {"task_id": "t4", "hard_checks": {"regression_pass": True}},
                {"task_id": "t5", "hard_checks": {"regression_pass": True}},
                {"task_id": "t6", "hard_checks": {"regression_pass": True}},
            ]
        }
        for idx, row in enumerate(attribution["rows"], start=1):
            row["task_id"] = f"t{idx}"

        payload = build_focus_queue(attribution_payload=attribution, top_k=2, run_results_payload=run_results)
        self.assertEqual(int(payload.get("queue_size", 0)), 2)
        queue = payload.get("queue") if isinstance(payload.get("queue"), list) else []
        self.assertEqual(str(queue[0].get("failure_type") or ""), "simulate_error")
        self.assertEqual(str(queue[0].get("gate_break_reason") or ""), "regression_fail")
        self.assertEqual(str(queue[1].get("failure_type") or ""), "semantic_regression")
        self.assertEqual(str(queue[1].get("gate_break_reason") or ""), "physics_contract_fail")

    def test_applies_persistence_bonus_for_consecutive_pair(self) -> None:
        attribution = {
            "rows": [
                {"task_id": "t1", "failure_type": "simulate_error", "gate_break_reason": "runtime_regression:4.1>3.6"},
            ]
        }
        run_results = {"records": [{"task_id": "t1", "hard_checks": {"regression_pass": False}}]}
        previous_entries = [
            {"queue": [{"failure_type": "simulate_error", "gate_break_reason": "regression_fail"}]},
            {"queue": [{"failure_type": "simulate_error", "gate_break_reason": "regression_fail"}]},
        ]
        payload = build_focus_queue(
            attribution_payload=attribution,
            run_results_payload=run_results,
            top_k=1,
            previous_entries=previous_entries,
            persistence_weight=2.5,
        )
        queue = payload.get("queue") if isinstance(payload.get("queue"), list) else []
        self.assertEqual(int(queue[0].get("streak_count", 0)), 2)
        self.assertEqual(float(queue[0].get("persistence_bonus", 0.0)), 5.0)


if __name__ == "__main__":
    unittest.main()
