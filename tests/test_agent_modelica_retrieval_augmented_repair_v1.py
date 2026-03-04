import unittest

from gateforge.agent_modelica_retrieval_augmented_repair_v1 import retrieve_repair_examples


class AgentModelicaRetrievalAugmentedRepairV1Tests(unittest.TestCase):
    def test_retrieves_similar_success_rows(self) -> None:
        history = {
            "rows": [
                {
                    "failure_type": "simulate_error",
                    "model_id": "LargeGrid",
                    "used_strategy": "sim_init_stability",
                    "action_trace": ["stabilize start values"],
                },
                {
                    "failure_type": "model_check_error",
                    "model_id": "MediumPlant",
                    "used_strategy": "mc_connection_consistency",
                    "action_trace": ["fix connector mismatch"],
                },
            ]
        }
        payload = retrieve_repair_examples(
            history_payload=history,
            failure_type="simulate_error",
            model_hint="LargeGrid.mo",
            top_k=2,
        )
        self.assertEqual(int(payload.get("retrieved_count", 0)), 1)
        actions = payload.get("suggested_actions") if isinstance(payload.get("suggested_actions"), list) else []
        self.assertIn("stabilize start values", actions)

    def test_prefers_successful_rows_when_labels_exist(self) -> None:
        history = {
            "rows": [
                {
                    "failure_type": "simulate_error",
                    "model_id": "LargeGrid",
                    "used_strategy": "sim_init_stability_fail",
                    "action_trace": ["unsafe step size"],
                    "status": "FAIL",
                },
                {
                    "failure_type": "simulate_error",
                    "model_id": "LargeGrid",
                    "used_strategy": "sim_init_stability_pass",
                    "action_trace": ["stabilize start values"],
                    "status": "PASS",
                },
            ]
        }
        payload = retrieve_repair_examples(
            history_payload=history,
            failure_type="simulate_error",
            model_hint="LargeGrid.mo",
            top_k=2,
        )
        self.assertEqual(int(payload.get("retrieved_count", 0)), 1)
        examples = payload.get("examples") if isinstance(payload.get("examples"), list) else []
        self.assertEqual(str(examples[0].get("success_state") or ""), "success")
        actions = payload.get("suggested_actions") if isinstance(payload.get("suggested_actions"), list) else []
        self.assertEqual(actions, ["stabilize start values"])


if __name__ == "__main__":
    unittest.main()
